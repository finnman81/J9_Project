#!/usr/bin/env python3
"""
Inspect upper-grade (5th–8th) sample data for sanity.

Prints:
- Counts of students per upper grade for the current demo year (default 2024-25)
- Sample students per grade with class/teacher
- Aggregate assessment counts for Reading (ORF) and Math (Math_Composite)

Usage:
    python scripts/inspect_upper_grade_data.py [--school-year 2024-25]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_db_connection  # type: ignore

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


UPPER_GRADES = ["Fifth", "Sixth", "Seventh", "Eighth"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect 5th–8th grade sample data.")
    parser.add_argument("--school-year", default="2024-25", help="School year to inspect (default: 2024-25).")
    args = parser.parse_args()

    school_year = args.school_year

    conn = get_db_connection()
    cur = conn.cursor()

    print(f"Inspecting upper-grade data for school_year={school_year!r}\n")

    # Students per grade
    cur.execute(
        """
        SELECT grade_level, COUNT(*) 
        FROM students
        WHERE school_year = %s AND grade_level = ANY(%s)
        GROUP BY grade_level
        ORDER BY grade_level
        """,
        (school_year, UPPER_GRADES),
    )
    rows = cur.fetchall()
    if not rows:
        print("No upper-grade students (Fifth–Eighth) found for this year.")
    else:
        print("Students per upper grade:")
        for grade, count in rows:
            print(f"  {grade}: {count}")

    # Sample students
    print("\nSample students (up to 5 per grade):")
    for grade in UPPER_GRADES:
        cur.execute(
            """
            SELECT student_name, class_name, teacher_name
            FROM students
            WHERE school_year = %s AND grade_level = %s
            ORDER BY student_name
            LIMIT 5
            """,
            (school_year, grade),
        )
        students = cur.fetchall()
        if not students:
            continue
        print(f"  {grade}:")
        for name, cls, teacher in students:
            print(f"    - {name} • {cls or '?'} • {teacher or '?'}")

    # Assessment counts for new students (Reading ORF / Math_Composite)
    print("\nAssessment counts for upper grades (Reading ORF / Math_Composite):")
    cur.execute(
        """
        SELECT s.grade_level,
               COUNT(*) FILTER (WHERE a.subject_area = 'Reading' AND a.assessment_type = 'ORF') AS reading_orf_count,
               COUNT(*) FILTER (WHERE a.subject_area = 'Math' AND a.assessment_type = 'Math_Composite') AS math_comp_count
        FROM students s
        LEFT JOIN assessments a
          ON a.student_id = s.student_id
         AND a.school_year = s.school_year
        WHERE s.school_year = %s
          AND s.grade_level = ANY(%s)
        GROUP BY s.grade_level
        ORDER BY s.grade_level
        """,
        (school_year, UPPER_GRADES),
    )
    rows = cur.fetchall()
    if not rows:
        print("  (no assessment rows found for upper grades)")
    else:
        for grade, reading_count, math_count in rows:
            print(f"  {grade}: Reading ORF={reading_count}, Math_Composite={math_count}")

    conn.close()


if __name__ == "__main__":
    main()

