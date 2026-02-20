#!/usr/bin/env python3
"""
Check for duplicate enrollments: students with multiple grade_level entries per school_year.

This identifies data quality issues where a student appears in multiple grades
within the same academic year, which shouldn't happen.
"""
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from core.database import get_db_connection  # type: ignore


def main():
    conn = get_db_connection()
    
    # Get all enrollments with student names
    df = pd.read_sql_query(
        """
        SELECT e.enrollment_id, s.display_name, e.grade_level, e.school_year, e.class_name, e.teacher_name
        FROM student_enrollments e
        JOIN students_core s ON s.student_uuid = e.student_uuid
        ORDER BY s.display_name, e.school_year, e.grade_level
        """,
        conn,
    )
    conn.close()
    
    if df.empty:
        print("No enrollments found.")
        return
    
    # Find students with multiple enrollments per year
    duplicates = df.groupby(['display_name', 'school_year']).size()
    dup_mask = duplicates > 1
    dup_students_years = duplicates[dup_mask]
    
    if len(dup_students_years) == 0:
        print("[OK] No duplicate enrollments found. Each student has at most one enrollment per school year.")
        return
    
    print(f"Found {len(dup_students_years)} student-year combinations with multiple enrollments:\n")
    
    # Show examples
    for (name, year), count in dup_students_years.head(20).items():
        rows = df[(df['display_name'] == name) & (df['school_year'] == year)]
        print(f"{name} ({year}): {count} enrollments")
        for _, row in rows.iterrows():
            print(f"  - {row['grade_level']} • {row['class_name']} • {row['teacher_name']} (enrollment_id: {row['enrollment_id']})")
        print()
    
    if len(dup_students_years) > 20:
        print(f"... and {len(dup_students_years) - 20} more")
    
    print(f"\nTotal duplicate enrollment rows: {dup_students_years.sum() - len(dup_students_years)}")


if __name__ == "__main__":
    main()
