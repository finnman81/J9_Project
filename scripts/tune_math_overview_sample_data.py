#!/usr/bin/env python
"""
Tune sample data for the Math Overview dashboard so KPIs look realistic.

This script is SAFE to run multiple times and is intended ONLY for sample data.
It adjusts Math assessment scores so that, for a chosen school year:

- `monitor_count` is close to a target (e.g. ~15)
- `needs_support_count` (Strategic + Intensive tiers) matches a target (e.g. 10)

How it works
------------
- Reads current KPIs from `api.routers.metrics.get_teacher_kpis`.
- Loads `v_support_status` for Math via `core.database.get_v_support_status`.
- For a subset of enrollments with valid thresholds it:
  - LOWERS scores below `support_threshold` to force **Needs Support**.
  - RAISES scores above `benchmark_threshold` to move students **out of Needs Support**
    when there are too many.
  - Optionally nudges some scores between thresholds to approximate the desired
    **Monitor** count.
- Applies updates by modifying the *latest* Math assessment per enrollment
  (the same ordering used in `v_teacher_roster`).

By default this is a DRY RUN: it only prints the changes it *would* make.
Use `--apply` to actually write to the database.

Usage
-----
    python scripts/tune_math_overview_sample_data.py \
        --school-year 2024-25 \
        --target-monitor 15 \
        --target-needs 10 \
        --by-grade \
        --apply

If `--school-year` is omitted, the script will:
- Call `dashboard_filters()` and use the first concrete school_year that is
  not "All", or fall back to "2024-25".
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from api.routers.dashboard import dashboard_filters  # type: ignore
from api.routers.metrics import get_teacher_kpis  # type: ignore
from core.database import get_db_connection, get_v_support_status  # type: ignore


@dataclass
class ScoreAdjustment:
    enrollment_id: str
    subject_area: str
    school_year: str
    old_score: float
    new_score: float
    reason: str


def _resolve_school_year(explicit: str | None) -> str:
    """Pick a concrete school year (not 'All') for tuning."""
    if explicit:
        return explicit
    try:
        f = dashboard_filters()
        years: List[str] = list(f.get("school_years", []))
        years = [y for y in years if y and y != "All"]
        if years:
            return years[0]
    except Exception:
        pass
    return "2024-25"


def _print_kpis(label: str, school_year: str) -> None:
    k = get_teacher_kpis(school_year=school_year, subject="Math")
    print(f"\n[{label}] Math KPIs for {school_year}:")
    print(
        f"  total_students={k['total_students']}, "
        f"monitor_count={k['monitor_count']} ({k['monitor_pct']}%), "
        f"needs_support_count={k['needs_support_count']} ({k['needs_support_pct']}%)"
    )


def _load_support_status(school_year: str) -> pd.DataFrame:
    """Load v_support_status rows for Math + given school_year, with thresholds."""
    df = get_v_support_status(
        teacher_name=None,
        school_year=school_year,
        subject_area="Math",
        grade_level=None,
        class_name=None,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    # Keep only rows where we have a latest_score and thresholds to reason about
    df = df.copy()
    df = df[df["latest_score"].notna()]
    if "support_threshold" in df.columns and "benchmark_threshold" in df.columns:
        df = df[df["support_threshold"].notna() & df["benchmark_threshold"].notna()]
    return df


def _plan_adjustments_for_needs(
    df: pd.DataFrame, target_needs: int
) -> list[ScoreAdjustment]:
    """Plan adjustments to hit a target number of Needs Support students."""
    adjustments: list[ScoreAdjustment] = []
    if df.empty:
        return adjustments

    # Current classification (mirror logic from v_support_status).
    tier = df["tier"].astype(str)
    needs_mask = tier.isin(["Intensive", "Strategic"])
    current_needs = int(needs_mask.sum())
    delta = target_needs - current_needs

    print(f"\nPlanning Needs Support adjustments: current={current_needs}, target={target_needs}, delta={delta}")

    if delta == 0:
        print("  Needs Support already at target; no changes planned.")
        return adjustments

    if delta > 0:
        # Need more Needs Support: take students currently not in Needs Support and
        # lower their scores below support_threshold.
        candidates = df[~needs_mask].copy()
        if candidates.empty:
            print("  No candidates available to move into Needs Support.")
            return adjustments
        # Sort by latest_score descending so we mostly lower higher-scoring students (for realism)
        candidates = candidates.sort_values(by="latest_score", ascending=False)
        for _, row in candidates.head(delta).iterrows():
            support_th = float(row["support_threshold"])
            old = float(row["latest_score"])
            new = support_th - 1.0  # clearly below support threshold
            adjustments.append(
                ScoreAdjustment(
                    enrollment_id=str(row["enrollment_id"]),
                    subject_area=str(row["subject_area"]),
                    school_year=str(row["school_year"]),
                    old_score=old,
                    new_score=new,
                    reason="move_to_needs_support",
                )
            )
    else:
        # Too many Needs Support students: move some up to On Track by raising scores
        # above benchmark_threshold.
        moves_needed = abs(delta)
        candidates = df[needs_mask].copy()
        if candidates.empty:
            print("  No Needs Support rows available to move out.")
            return adjustments
        # Sort by latest_score ascending so we "rescue" highest-scoring students first
        candidates = candidates.sort_values(by="latest_score", ascending=False)
        for _, row in candidates.head(moves_needed).iterrows():
            bench_th = float(row["benchmark_threshold"])
            old = float(row["latest_score"])
            new = bench_th + 1.0  # clearly at/above benchmark
            adjustments.append(
                ScoreAdjustment(
                    enrollment_id=str(row["enrollment_id"]),
                    subject_area=str(row["subject_area"]),
                    school_year=str(row["school_year"]),
                    old_score=old,
                    new_score=new,
                    reason="move_out_of_needs_support",
                )
            )

    return adjustments


def _plan_adjustments_for_monitor(
    df: pd.DataFrame, target_monitor: int
) -> list[ScoreAdjustment]:
    """Plan approximate adjustments for Monitor count.

    This is best-effort: we try to move students into the Monitor band
    (between support and benchmark thresholds) or out of it.
    """
    adjustments: list[ScoreAdjustment] = []
    if df.empty:
        return adjustments

    support_status = df["support_status"].astype(str)
    monitor_mask = support_status == "Monitor"
    current_monitor = int(monitor_mask.sum())
    delta = target_monitor - current_monitor

    print(f"\nPlanning Monitor adjustments: current={current_monitor}, target={target_monitor}, delta={delta}")

    if delta == 0:
        print("  Monitor already at target; no changes planned.")
        return adjustments

    if delta > 0:
        # Need more Monitor: take some On Track or Needs Support rows and move them into band.
        candidates = df[~monitor_mask].copy()
        if candidates.empty:
            print("  No candidates available to move into Monitor.")
            return adjustments
        candidates = candidates.sort_values(by="latest_score", ascending=False)
        for _, row in candidates.head(delta).iterrows():
            support_th = float(row["support_threshold"])
            bench_th = float(row["benchmark_threshold"])
            # Place new score midway between thresholds.
            mid = (support_th + bench_th) / 2.0
            old = float(row["latest_score"])
            adjustments.append(
                ScoreAdjustment(
                    enrollment_id=str(row["enrollment_id"]),
                    subject_area=str(row["subject_area"]),
                    school_year=str(row["school_year"]),
                    old_score=old,
                    new_score=mid,
                    reason="move_into_monitor_band",
                )
            )
    else:
        # Too many Monitor rows: move some up to On Track by raising above benchmark.
        moves_needed = abs(delta)
        candidates = df[monitor_mask].copy()
        if candidates.empty:
            print("  No Monitor rows available to move out.")
            return adjustments
        candidates = candidates.sort_values(by="latest_score", ascending=False)
        for _, row in candidates.head(moves_needed).iterrows():
            bench_th = float(row["benchmark_threshold"])
            old = float(row["latest_score"])
            new = bench_th + 1.0
            adjustments.append(
                ScoreAdjustment(
                    enrollment_id=str(row["enrollment_id"]),
                    subject_area=str(row["subject_area"]),
                    school_year=str(row["school_year"]),
                    old_score=old,
                    new_score=new,
                    reason="move_out_of_monitor_band",
                )
            )

    return adjustments


def _apply_adjustments(adjustments: list[ScoreAdjustment], dry_run: bool = True) -> None:
    """Apply score adjustments to the latest Math assessment per enrollment."""
    if not adjustments:
        print("\nNo score adjustments to apply.")
        return

    print(f"\nPlanned adjustments ({'DRY RUN' if dry_run else 'APPLYING'}):")
    for adj in adjustments:
        print(
            f"  enrollment={adj.enrollment_id} "
            f"subject={adj.subject_area} year={adj.school_year} "
            f"{adj.old_score} -> {adj.new_score} ({adj.reason})"
        )

    if dry_run:
        print("\nDry run only. Re-run with --apply to write these changes.")
        return

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for adj in adjustments:
            # Find the latest assessment row matching the v_teacher_roster ordering.
            cur.execute(
                """
                SELECT assessment_id
                FROM public.assessments
                WHERE enrollment_id = %s
                  AND subject_area = %s
                ORDER BY effective_date DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (adj.enrollment_id, adj.subject_area),
            )
            row = cur.fetchone()
            if not row:
                print(f"  ! Skipping enrollment {adj.enrollment_id}: no assessments found.")
                continue
            assessment_id = row[0]
            cur.execute(
                """
                UPDATE public.assessments
                SET score_normalized = %s
                WHERE assessment_id = %s
                """,
                (adj.new_score, assessment_id),
            )
        conn.commit()
        print("\nUpdates committed.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune Math Overview KPIs for sample data.")
    parser.add_argument("--school-year", help="Concrete school year to tune (e.g. 2024-25). Default: first non-'All' from dashboard filters.")
    parser.add_argument("--target-monitor", type=int, default=15, help="Target Monitor count (approximate, global). Default: 15.")
    parser.add_argument("--target-needs", type=int, default=10, help="Global fallback target Needs Support count (if grade-level targets not used).")
    parser.add_argument(
        "--by-grade",
        action="store_true",
        help="Scale Needs Support by grade level (e.g., ~30%% in K/1, decreasing toward 8th).",
    )
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run).")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: Set DATABASE_URL in .env or environment.")
        sys.exit(1)

    school_year = _resolve_school_year(args.school_year)
    print(f"Tuning Math Overview for school_year={school_year!r}")

    _print_kpis("BEFORE", school_year)

    df = _load_support_status(school_year)
    if df.empty:
        print("\nNo v_support_status rows found for Math; nothing to tune.")
        return

    # Plan changes in two passes: Needs Support first (hard target), then Monitor (approx).
    # If --by-grade is set, compute grade-specific targets so lower grades have
    # higher Needs Support and upper grades have fewer students in support.
    needs_adjustments: list[ScoreAdjustment] = []
    if args.by_grade and "grade_level" in df.columns:
        # Default target percentages by grade (roughly 30–20%, tapering down;
        # upper grades still have some students flagged as needing support).
        target_pct_by_grade: dict[str, float] = {
            "Kindergarten": 0.30,
            "First": 0.30,
            "Second": 0.28,
            "Third": 0.26,
            "Fourth": 0.24,
            "Fifth": 0.22,
            "Sixth": 0.20,
            "Seventh": 0.18,
            "Eighth": 0.15,
        }
        for grade in sorted(df["grade_level"].dropna().unique()):
            sub = df[df["grade_level"] == grade]
            total_g = len(sub)
            if total_g == 0:
                continue
            pct = target_pct_by_grade.get(str(grade), args.target_needs / max(1, len(df)))
            pct = max(0.0, min(0.9, pct))
            target_g = int(round(total_g * pct))
            if target_g <= 0:
                continue
            print(f"\n--- Grade {grade}: total={total_g}, target Needs Support~{target_g} ({pct*100:.1f}%)")
            needs_adjustments.extend(_plan_adjustments_for_needs(sub, target_needs=target_g))
    else:
        needs_adjustments = _plan_adjustments_for_needs(df, target_needs=args.target_needs)

    # Apply Needs Support adjustments to a copy of df to better approximate Monitor planning.
    df_after_needs = df.copy()
    if needs_adjustments:
        by_enrollment = {adj.enrollment_id: adj for adj in needs_adjustments}
        mask = df_after_needs["enrollment_id"].astype(str).isin(by_enrollment.keys())
        for idx in df_after_needs[mask].index:
            eid = str(df_after_needs.at[idx, "enrollment_id"])
            df_after_needs.at[idx, "latest_score"] = by_enrollment[eid].new_score

    monitor_adjustments = _plan_adjustments_for_monitor(df_after_needs, target_monitor=args.target_monitor)

    # Combine and deduplicate adjustments per enrollment (last one wins).
    all_adjustments: dict[str, ScoreAdjustment] = {}
    for adj in needs_adjustments + monitor_adjustments:
        all_adjustments[adj.enrollment_id] = adj

    final_adjustments = list(all_adjustments.values())
    _apply_adjustments(final_adjustments, dry_run=not args.apply)

    if args.apply and final_adjustments:
        # Re-print KPIs after changes.
        _print_kpis("AFTER", school_year)


if __name__ == "__main__":
    main()
