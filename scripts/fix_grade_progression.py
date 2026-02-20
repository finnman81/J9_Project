#!/usr/bin/env python3
"""
Fix grade progression issues: ensure students progress one grade per year.

For students who appear to repeat a grade (same grade in consecutive years),
update the later year's enrollment to the next grade level to represent normal progression.

This is a data quality fix for sample data. Safe to run multiple times.
By default, this is a DRY RUN. Use --apply to make changes.

Usage:
    python scripts/fix_grade_progression.py [--apply]
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

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

GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth']
GRADE_TO_INDEX = {g: i for i, g in enumerate(GRADE_ORDER)}


def get_next_grade(grade: str) -> Optional[str]:
    """Get the next grade in progression."""
    idx = GRADE_TO_INDEX.get(grade)
    if idx is None or idx >= len(GRADE_ORDER) - 1:
        return None
    return GRADE_ORDER[idx + 1]


def main():
    parser = argparse.ArgumentParser(description="Fix grade progression issues.")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run).")
    args = parser.parse_args()
    
    if "DATABASE_URL" not in os.environ:
        print("ERROR: Set DATABASE_URL in .env or environment.")
        sys.exit(1)
    
    conn = get_db_connection()
    
    # Get all enrollments ordered by student and year
    df = pd.read_sql_query(
        """
        SELECT e.enrollment_id, s.display_name, e.student_uuid, e.grade_level, e.school_year, e.class_name, e.teacher_name
        FROM student_enrollments e
        JOIN students_core s ON s.student_uuid = e.student_uuid
        ORDER BY s.display_name, e.school_year
        """,
        conn,
    )
    
    if df.empty:
        print("No enrollments found.")
        conn.close()
        return
    
    # Find progression issues: same grade in consecutive years
    fixes_needed = []
    
    for student_uuid in df['student_uuid'].unique():
        student_enrollments = df[df['student_uuid'] == student_uuid].sort_values('school_year')
        student_name = student_enrollments.iloc[0]['display_name']
        
        prev_grade = None
        prev_year = None
        
        for _, row in student_enrollments.iterrows():
            current_grade = row['grade_level']
            current_year = row['school_year']
            
            if prev_grade and prev_year:
                # Check if this is a repeat (same grade in consecutive years)
                if current_grade == prev_grade:
                    next_grade = get_next_grade(current_grade)
                    if next_grade:
                        fixes_needed.append({
                            'enrollment_id': row['enrollment_id'],
                            'student_name': student_name,
                            'school_year': current_year,
                            'current_grade': current_grade,
                            'new_grade': next_grade,
                            'class_name': row['class_name'],
                            'teacher_name': row['teacher_name'],
                        })
                        # Update prev_grade to the fixed grade for next iteration
                        prev_grade = next_grade
                    else:
                        # Can't progress further (already at Eighth)
                        prev_grade = current_grade
                else:
                    prev_grade = current_grade
            else:
                prev_grade = current_grade
            
            prev_year = current_year
    
    if not fixes_needed:
        print("[OK] No grade progression issues found. All students progress normally.")
        conn.close()
        return
    
    print(f"Found {len(fixes_needed)} enrollment(s) with grade progression issues.\n")
    print(f"{'DRY RUN' if not args.apply else 'APPLYING CHANGES'}...\n")
    
    cur = conn.cursor()
    for fix in fixes_needed:
        print(
            f"{fix['student_name']} ({fix['school_year']}): "
            f"{fix['current_grade']} -> {fix['new_grade']} "
            f"(enrollment_id: {fix['enrollment_id']})"
        )
        
        if args.apply:
            cur.execute(
                """
                UPDATE student_enrollments
                SET grade_level = %s
                WHERE enrollment_id = %s
                """,
                (fix['new_grade'], fix['enrollment_id']),
            )
    
    if args.apply:
        conn.commit()
        print(f"\n[OK] Updated {len(fixes_needed)} enrollment(s) to fix grade progression.")
    else:
        print(f"\nDry run complete. Re-run with --apply to make these changes.")
    
    conn.close()


if __name__ == "__main__":
    main()
