#!/usr/bin/env python3
"""
Add benchmark_thresholds rows for upper-grade Reading (5th–8th).

This ensures v_support_status can compute Tier / Needs Support for 5th–8th
Reading enrollments, so the dashboard and tuning script can include them.

Logic:
- Find distinct (subject_area, assessment_type, grade_level, assessment_period, school_year)
  combinations for Reading assessments where the enrollment's grade is 5th–8th.
- For each combination that does NOT already exist in benchmark_thresholds,
  insert a default support_threshold / benchmark_threshold (40 / 70).

Safe to run multiple times; it only inserts missing combinations.

Usage:
    python scripts/add_upper_grade_reading_thresholds.py
"""

import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


UPPER_GRADES = ("Fifth", "Sixth", "Seventh", "Eighth")


def main() -> None:
    if "DATABASE_URL" not in os.environ:
        raise SystemExit("DATABASE_URL not set; add it to .env or environment.")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()

    # Distinct Reading assessment combos for 5th–8th with enrollments wired up.
    cur.execute(
        """
        SELECT DISTINCT a.subject_area,
                        a.assessment_type,
                        e.grade_level,
                        a.assessment_period,
                        a.school_year
        FROM assessments a
        JOIN student_enrollments e ON e.enrollment_id = a.enrollment_id
        WHERE a.enrollment_id IS NOT NULL
          AND a.subject_area = 'Reading'
          AND e.grade_level = ANY(%s)
        """,
        (list(UPPER_GRADES),),
    )
    rows = cur.fetchall()
    if not rows:
        print("No Reading assessments found for upper grades with enrollments; nothing to do.")
        conn.close()
        return

    # Existing benchmark_thresholds for these combos.
    cur.execute(
        """
        SELECT subject_area,
               assessment_type,
               grade_level,
               assessment_period,
               school_year
        FROM benchmark_thresholds
        WHERE subject_area = 'Reading'
          AND grade_level = ANY(%s)
        """,
        (list(UPPER_GRADES),),
    )
    existing_keys = {
        (r[0], r[1], r[2], r[3], r[4])
        for r in cur.fetchall()
    }

    support_pct, benchmark_pct = 40.0, 70.0
    to_insert = []
    for subj, atype, grade, period, year in rows:
        key = (subj, atype, grade, period, year)
        if key in existing_keys:
            continue
        to_insert.append((subj, atype, grade, period, year, support_pct, benchmark_pct))

    if not to_insert:
        print("All upper-grade Reading benchmark_thresholds already present; nothing to insert.")
        conn.close()
        return

    execute_values(
        cur,
        """
        INSERT INTO benchmark_thresholds
            (subject_area, assessment_type, grade_level, assessment_period, school_year,
             support_threshold, benchmark_threshold)
        VALUES %s
        """,
        to_insert,
    )
    conn.commit()
    conn.close()

    print(f"Inserted {len(to_insert)} new upper-grade Reading benchmark_threshold rows.")


if __name__ == "__main__":
    main()

