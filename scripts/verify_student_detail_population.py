#!/usr/bin/env python3
"""
Loop through enrollments and report what's populated for Student Detail:
Tier/Risk, Trend, Interventions, Notes, Goals.

Run before manual UI check to confirm data is returned by the backend.
Usage: python scripts/verify_student_detail_population.py [--limit N] [--math-only]

Note: The Math Student Detail page in the UI uses GET /api/student-detail/{student_uuid}?subject=Math
(aggregated across enrollments). This script checks per-enrollment data; the integration tests
in tests/test_student_detail_data.py also cover the student-detail-by-UUID path for multiple names.

Requires: DATABASE_URL in .env or environment.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="Verify Student Detail data population")
    parser.add_argument("--limit", type=int, default=20, help="Max enrollments to check (default 20)")
    parser.add_argument("--math-only", action="store_true", help="Only show enrollments with Math assessments")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: Set DATABASE_URL in .env or environment.")
        sys.exit(1)

    from core.database import (
        get_db_connection,
        get_enrollment,
        get_enrollment_support_status,
        get_enrollment_growth,
        get_enrollment_interventions,
        get_enrollment_notes,
        get_enrollment_goals,
    )

    # Enrollments that have at least one Math assessment (so we care about Math tier/trend)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT a.enrollment_id
            FROM assessments a
            WHERE a.enrollment_id IS NOT NULL
            ORDER BY a.enrollment_id
            LIMIT %s
        """, (args.limit * 3,))  # fetch more then filter by math if needed
        all_eids = [str(r[0]) for r in cur.fetchall()]
        if args.math_only:
            cur.execute("""
                SELECT DISTINCT enrollment_id FROM assessments
                WHERE enrollment_id IS NOT NULL AND subject_area = 'Math'
                LIMIT %s
            """, (args.limit,))
            all_eids = [str(r[0]) for r in cur.fetchall()]
        else:
            all_eids = all_eids[: args.limit]
    finally:
        conn.close()

    if not all_eids:
        print("No enrollments found.")
        return

    print(f"Checking {len(all_eids)} enrollment(s). Subject: Math (Tier/Risk, Trend).\n")
    print("-" * 100)
    ok_tier = 0
    ok_trend = 0
    ok_int = 0
    ok_notes = 0
    ok_goals = 0

    for i, eid in enumerate(all_eids):
        en = get_enrollment(eid)
        name = (en or {}).get("display_name") or "?"
        support = get_enrollment_support_status(eid, "Math")
        growth_year = (en or {}).get("school_year")
        growth = get_enrollment_growth(eid, "Math", school_year=growth_year)
        interventions = get_enrollment_interventions(eid)
        notes = get_enrollment_notes(eid)
        goals = get_enrollment_goals(eid)

        tier = (support.get("tier") if support else None) or "—"
        trend = (growth.get("trend") if growth else None) or "—"
        n_int = 0 if interventions is None or (hasattr(interventions, "empty") and interventions.empty) else len(interventions)
        n_notes = 0 if notes is None or (hasattr(notes, "empty") and notes.empty) else len(notes)
        n_goals = 0 if goals is None or (hasattr(goals, "empty") and goals.empty) else len(goals)

        if support and support.get("tier"):
            ok_tier += 1
        if growth and growth.get("trend"):
            ok_trend += 1
        if n_int > 0:
            ok_int += 1
        if n_notes > 0:
            ok_notes += 1
        if n_goals > 0:
            ok_goals += 1

        print(f"{i+1}. {name} ({eid[:8]}...)")
        print(f"   Tier/Risk: {tier}  |  Trend: {trend}  |  Interventions: {n_int}  |  Notes: {n_notes}  |  Goals: {n_goals}")
        print()

    print("-" * 100)
    print(f"Summary: Tier/Risk populated: {ok_tier}/{len(all_eids)}  |  Trend: {ok_trend}/{len(all_eids)}  |  Interventions: {ok_int}  |  Notes: {ok_notes}  |  Goals: {ok_goals}")
    if ok_tier == 0 and len(all_eids) > 0:
        print("\nTip: Re-apply v_teacher_roster (and v_support_status) in Supabase SQL Editor so Math rows appear.")
    if ok_trend == 0 and len(all_eids) > 0:
        print("Tip: Trend needs 2+ assessments per enrollment/subject/year; run generate_sample_tier_trend_interventions_goals_notes.py to add prior assessments.")
    print("Done. If numbers look good, run the app and check the Math Student Detail page in the UI.")


if __name__ == "__main__":
    main()
