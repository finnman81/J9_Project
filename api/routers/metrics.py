"""
Metrics API: teacher KPIs, priority students, growth, distribution.
Uses SQL views v_support_status, v_priority_students, v_growth_last_two.
"""
import pandas as pd
from fastapi import APIRouter, HTTPException

from core.database import (
    get_v_support_status,
    get_v_priority_students,
    get_v_growth_last_two,
    get_benchmark_thresholds,
)
from api.serializers import dataframe_to_records

router = APIRouter()

# Grade order for charts and filters: Kindergarten → First → Second → Third → Fourth
GRADE_ORDER = ["Kindergarten", "First", "Second", "Third", "Fourth"]


def _kpis_from_support_status(
    df: pd.DataFrame,
    current_period: str | None = None,
    current_school_year: str | None = None,
):
    """Compute KPI strip from v_support_status rows. Optional current_period/current_school_year for 'assessed this window'."""
    empty = {
        "total_students": 0,
        "assessed_students": 0,
        "assessed_pct": 0.0,
        "monitor_count": 0,
        "monitor_pct": 0.0,
        "needs_support_count": 0,
        "needs_support_pct": 0.0,
        "support_gap_count": 0,
        "support_gap_pct": 0.0,
        "overdue_count": 0,
        "overdue_pct": 0.0,
        "median_days_since_assessment": None,
        "intervention_coverage_count": 0,
        "intervention_coverage_pct": 0.0,
        "assessed_this_window_count": 0,
        "assessed_this_window_pct": 0.0,
        "tier_moved_up_count": 0,
        "tier_moved_down_count": 0,
    }
    if df is None or df.empty:
        return empty
    total = len(df)
    assessed = df["latest_score"].notna().sum()
    # Support status: On Track / Monitor / Needs Support (tier: Core / Strategic / Intensive)
    support_status = df.get("support_status")
    monitor = (support_status == "Monitor").sum() if support_status is not None else 0
    needs = df["tier"].isin(["Intensive", "Strategic"]).sum()
    # Support gap = Needs Support with no active intervention
    need_df = df[df["tier"].isin(["Intensive", "Strategic"])]
    support_gap = (need_df["has_active_intervention"].eq(False).sum() if "has_active_intervention" in need_df.columns else 0) if not need_df.empty else 0
    covered = need_df["has_active_intervention"].eq(True).sum() if not need_df.empty else 0
    overdue = (df["days_since_assessment"] > 90).sum() if "days_since_assessment" in df.columns else 0
    days = df["days_since_assessment"].dropna()
    days = days[days >= 0]
    median_days = float(days.median()) if len(days) else None

    # Assessed this window: latest_period + school_year match
    assessed_window = 0
    period_col = df.get("latest_period")
    year_col = df.get("school_year")
    if period_col is not None and year_col is not None and current_period and current_school_year:
        in_window = (
            (period_col.astype(str).str.strip().str.lower() == current_period.strip().lower())
            & (year_col.astype(str) == current_school_year)
        )
        assessed_window = int(in_window.sum())
    assessed_window_pct = round(100.0 * assessed_window / total, 1) if total else 0.0

    return {
        "total_students": int(total),
        "assessed_students": int(assessed),
        "assessed_pct": round(100.0 * assessed / total, 1) if total else 0.0,
        "monitor_count": int(monitor),
        "monitor_pct": round(100.0 * monitor / total, 1) if total else 0.0,
        "needs_support_count": int(needs),
        "needs_support_pct": round(100.0 * needs / total, 1) if total else 0.0,
        "support_gap_count": int(support_gap),
        "support_gap_pct": round(100.0 * support_gap / total, 1) if total else 0.0,
        "overdue_count": int(overdue),
        "overdue_pct": round(100.0 * overdue / total, 1) if total else 0.0,
        "median_days_since_assessment": median_days,
        "intervention_coverage_count": int(covered),
        "intervention_coverage_pct": round(100.0 * covered / needs, 1) if needs else 0.0,
        "assessed_this_window_count": int(assessed_window),
        "assessed_this_window_pct": assessed_window_pct,
        "tier_moved_up_count": 0,
        "tier_moved_down_count": 0,
    }


@router.get("/metrics/teacher-kpis")
def get_teacher_kpis(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
    current_period: str | None = None,
    current_school_year: str | None = None,
):
    """Return KPI strip. Use current_period + current_school_year for '%% assessed this window' (e.g. Fall, 2024-25)."""
    try:
        df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        return _kpis_from_support_status(
            df,
            current_period=current_period or None,
            current_school_year=current_school_year or school_year,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _reasons_to_chips(reasons: str | None) -> list[str]:
    """Split reasons string into chips: Overdue, Declining, No intervention, Below benchmark."""
    if not reasons or not str(reasons).strip():
        return []
    chips = []
    s = str(reasons).lower()
    if "overdue" in s:
        chips.append("Overdue")
    if "declining" in s:
        chips.append("Declining")
    if "no active intervention" in s or "no intervention" in s:
        chips.append("No intervention")
    if "intensive tier" in s or "strategic tier" in s or "below benchmark" in s:
        chips.append("Below benchmark")
    return chips if chips else [r.strip() for r in reasons.split("|") if r.strip()][:4]


@router.get("/metrics/priority-students")
def get_priority_students(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return priority students: support_status, reason_chips, default sort (support gap > declining > overdue > lowest score)."""
    try:
        df = get_v_priority_students(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None or df.empty:
            return {
                "rows": [],
                "flagged_intensive": 0,
                "flagged_strategic": 0,
                "total_flagged": 0,
            }
        # Default sort: Needs Support + no intervention > Declining > Overdue > lowest score
        df = df.copy()
        support_gap = (
            df["tier"].isin(["Intensive", "Strategic"]) & (df["has_active_intervention"].eq(False))
        )
        declining = (df.get("trend") == "Declining") if "trend" in df.columns else pd.Series(False, index=df.index)
        overdue = (df["days_since_assessment"] > 90) if "days_since_assessment" in df.columns else pd.Series(False, index=df.index)
        df["_sort1"] = (~support_gap).astype(int)
        df["_sort2"] = (~declining).astype(int)
        df["_sort3"] = (~overdue).astype(int)
        df["_sort4"] = df["latest_score"].fillna(999)
        df = df.sort_values(by=["_sort1", "_sort2", "_sort3", "_sort4"], ascending=[True, True, True, True])
        df = df.drop(columns=["_sort1", "_sort2", "_sort3", "_sort4"], errors="ignore")

        flagged = df[df["priority_score"] > 0] if "priority_score" in df.columns else df
        intensive = (flagged["tier"] == "Intensive").sum() if not flagged.empty else 0
        strategic = (flagged["tier"] == "Strategic").sum() if not flagged.empty else 0
        rows_raw = dataframe_to_records(df)
        rows = []
        for r in rows_raw:
            reasons_str = r.get("reasons")
            chips = _reasons_to_chips(reasons_str)
            rows.append({**r, "reason_chips": chips})
        return {
            "rows": rows,
            "flagged_intensive": int(intensive),
            "flagged_strategic": int(strategic),
            "total_flagged": len(flagged),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/growth")
def get_growth_metrics(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return growth KPIs (median_growth, pct_improving, pct_declining, n) from last-two view."""
    try:
        df = get_v_growth_last_two(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None or df.empty or "growth" not in df.columns:
            return {
                "median_growth": None,
                "pct_improving": 0.0,
                "pct_declining": 0.0,
                "students_with_growth_data": 0,
            }
        growth = df["growth"].dropna()
        n = len(growth)
        if n == 0:
            return {
                "median_growth": None,
                "pct_improving": 0.0,
                "pct_declining": 0.0,
                "students_with_growth_data": 0,
            }
        trend = df["trend"] if "trend" in df.columns else pd.Series(dtype=object)
        improving = (trend == "Improving").sum()
        declining = (trend == "Declining").sum()
        return {
            "median_growth": round(float(growth.median()), 1),
            "pct_improving": round(100.0 * improving / n, 1),
            "pct_declining": round(100.0 * declining / n, 1),
            "students_with_growth_data": n,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/distribution")
def get_distribution(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return histogram bins, benchmark/support thresholds, and avg by grade."""
    try:
        df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        scores = df["latest_score"].dropna() if df is not None and not df.empty else pd.Series(dtype=float)
        bins = []
        total_scores = len(scores)
        if total_scores > 0:
            for low in range(0, 100, 10):
                high = low + 10
                count = ((scores >= low) & (scores < high)).sum()
                pct = round(100.0 * count / total_scores, 1)
                bins.append({"bin_min": low, "bin_max": high, "count": int(count), "pct": pct})
            count_100 = (scores >= 100).sum()
            if count_100 > 0:
                pct_100 = round(100.0 * count_100 / total_scores, 1)
                bins.append({"bin_min": 100, "bin_max": 110, "count": int(count_100), "pct": pct_100})
        avg_by_grade = []
        if df is not None and not df.empty and "grade_level" in df.columns:
            needs = df["tier"].isin(["Intensive", "Strategic"]) if "tier" in df.columns else pd.Series(False, index=df.index)
            df_grp = df.assign(_needs=needs)
            grp = df_grp.groupby("grade_level").agg(
                average_score=("latest_score", "mean"),
                total=("latest_score", "count"),
                needs_count=("_needs", "sum"),
            ).reset_index()
            grp["pct_needs_support"] = (100.0 * grp["needs_count"] / grp["total"].replace(0, 1)).round(1)
            grp = grp.drop(columns=["total", "needs_count"], errors="ignore")
            order = {g: i for i, g in enumerate(GRADE_ORDER)}
            grp["_order"] = grp["grade_level"].map(lambda x: order.get(x, 99))
            grp = grp.sort_values("_order").drop(columns=["_order"], errors="ignore")
            avg_by_grade = dataframe_to_records(grp)
        thresholds_df = get_benchmark_thresholds(
            subject_area=subject,
            school_year=school_year,
        )
        support_threshold = None
        benchmark_threshold = None
        if thresholds_df is not None and not thresholds_df.empty:
            support_threshold = float(thresholds_df["support_threshold"].median()) if "support_threshold" in thresholds_df.columns else None
            benchmark_threshold = float(thresholds_df["benchmark_threshold"].median()) if "benchmark_threshold" in thresholds_df.columns else None
        return {
            "bins": bins,
            "avg_by_grade": avg_by_grade,
            "support_threshold": support_threshold,
            "benchmark_threshold": benchmark_threshold,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
