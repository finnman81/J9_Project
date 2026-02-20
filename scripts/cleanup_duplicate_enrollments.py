#!/usr/bin/env python3
"""
Clean up duplicate enrollments: keep one enrollment per student per school year.

For each (student_uuid, school_year) pair with multiple enrollments:
- Keep the enrollment with the most assessments (or most recent if tied)
- Migrate assessments/interventions/notes/goals from duplicates to the kept enrollment
- Delete duplicate enrollments

Safe to run multiple times (idempotent). By default, this is a DRY RUN.
Use --apply to actually make changes.

Usage:
    python scripts/cleanup_duplicate_enrollments.py [--apply]
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


def find_duplicate_enrollments(conn) -> List[Tuple[str, str]]:
    """Find (student_uuid, school_year) pairs with multiple enrollments."""
    df = pd.read_sql_query(
        """
        SELECT e.student_uuid, e.school_year, COUNT(*) as cnt
        FROM student_enrollments e
        GROUP BY e.student_uuid, e.school_year
        HAVING COUNT(*) > 1
        ORDER BY e.student_uuid, e.school_year
        """,
        conn,
    )
    return [(row['student_uuid'], row['school_year']) for _, row in df.iterrows()]


def choose_enrollment_to_keep(conn, student_uuid: str, school_year: str) -> str:
    """Choose which enrollment_id to keep for a student-year pair.
    
    Strategy: Prefer enrollment that represents normal grade progression (one grade higher per year).
    If no clear progression match, fall back to enrollment with most assessments, then most recent.
    """
    cur = conn.cursor()
    
    GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth']
    grade_to_index = {g: i for i, g in enumerate(GRADE_ORDER)}
    
    # Get all enrollments for this student-year
    cur.execute(
        """
        SELECT e.enrollment_id, e.grade_level, e.class_name, e.created_at
        FROM student_enrollments e
        WHERE e.student_uuid = %s AND e.school_year = %s
        ORDER BY e.created_at DESC
        """,
        (student_uuid, school_year),
    )
    enrollments = cur.fetchall()
    
    if not enrollments:
        return None
    
    if len(enrollments) == 1:
        return enrollments[0][0]
    
    # Get student's enrollments from previous year to infer expected grade progression
    cur.execute(
        """
        SELECT e.grade_level, e.school_year
        FROM student_enrollments e
        WHERE e.student_uuid = %s
          AND e.school_year < %s
        ORDER BY e.school_year DESC
        LIMIT 1
        """,
        (student_uuid, school_year),
    )
    prev_row = cur.fetchone()
    expected_grade = None
    if prev_row:
        prev_grade = prev_row[0]
        prev_idx = grade_to_index.get(prev_grade)
        if prev_idx is not None and prev_idx < len(GRADE_ORDER) - 1:
            expected_grade = GRADE_ORDER[prev_idx + 1]  # Next grade up
    
    # Count assessments per enrollment
    enrollment_ids = [e[0] for e in enrollments]
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    cur.execute(
        f"""
        SELECT enrollment_id, COUNT(*) as assessment_count
        FROM assessments
        WHERE enrollment_id IN ({placeholders})
        GROUP BY enrollment_id
        """,
        enrollment_ids,
    )
    assessment_counts = {row[0]: row[1] for row in cur.fetchall()}
    
    # Score each enrollment: prefer expected grade, then assessment count, then recency
    enrollments_scored = []
    for e in enrollments:
        eid, grade, _, created_at = e
        score = 0
        # Bonus for matching expected progression
        if expected_grade and grade == expected_grade:
            score += 1000
        # Add assessment count (scaled)
        score += assessment_counts.get(eid, 0) * 10
        # Add recency bonus (newer = higher)
        enrollments_scored.append((eid, score, created_at))
    
    enrollments_scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    return enrollments_scored[0][0]  # enrollment_id to keep


def migrate_data_to_enrollment(
    conn, from_enrollment_id: str, to_enrollment_id: str, dry_run: bool
) -> Dict[str, int]:
    """Migrate assessments, interventions, notes, goals from one enrollment to another.
    
    For assessments: only migrate those that won't create duplicates (unique constraint).
    Delete duplicate assessments from source enrollment.
    
    Returns dict with counts of migrated/deleted rows.
    """
    cur = conn.cursor()
    counts = {}
    
    # Migrate assessments (only those that won't create duplicates)
    # First, find assessments that would create duplicates
    cur.execute(
        """
        SELECT a.assessment_id
        FROM assessments a
        WHERE a.enrollment_id = %s
          AND EXISTS (
            SELECT 1 FROM assessments a2
            WHERE a2.enrollment_id = %s
              AND a2.subject_area = a.subject_area
              AND a2.assessment_type = a.assessment_type
              AND a2.assessment_period = a.assessment_period
              AND a2.school_year = a.school_year
          )
        """,
        (from_enrollment_id, to_enrollment_id),
    )
    duplicate_assessment_ids = [row[0] for row in cur.fetchall()]
    
    # Delete duplicate assessments from source (they're redundant)
    if duplicate_assessment_ids:
        placeholders = ','.join(['%s'] * len(duplicate_assessment_ids))
        cur.execute(
            f"""
            DELETE FROM assessments
            WHERE assessment_id IN ({placeholders})
            """,
            duplicate_assessment_ids,
        )
        counts['assessments_deleted'] = cur.rowcount
    
    # Migrate non-duplicate assessments
    cur.execute(
        """
        UPDATE assessments
        SET enrollment_id = %s
        WHERE enrollment_id = %s
        """,
        (to_enrollment_id, from_enrollment_id),
    )
    counts['assessments'] = cur.rowcount
    
    # Migrate interventions
    cur.execute(
        """
        UPDATE interventions
        SET enrollment_id = %s
        WHERE enrollment_id = %s
        """,
        (to_enrollment_id, from_enrollment_id),
    )
    counts['interventions'] = cur.rowcount
    
    # Migrate teacher_notes
    cur.execute(
        """
        UPDATE teacher_notes
        SET enrollment_id = %s
        WHERE enrollment_id = %s
        """,
        (to_enrollment_id, from_enrollment_id),
    )
    counts['notes'] = cur.rowcount
    
    # Migrate student_goals
    cur.execute(
        """
        UPDATE student_goals
        SET enrollment_id = %s
        WHERE enrollment_id = %s
        """,
        (to_enrollment_id, from_enrollment_id),
    )
    counts['goals'] = cur.rowcount
    
    if not dry_run:
        conn.commit()
    
    return counts


def main():
    parser = argparse.ArgumentParser(description="Clean up duplicate enrollments per student per year.")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run).")
    args = parser.parse_args()
    
    if "DATABASE_URL" not in os.environ:
        print("ERROR: Set DATABASE_URL in .env or environment.")
        sys.exit(1)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    duplicates = find_duplicate_enrollments(conn)
    
    if not duplicates:
        print("[OK] No duplicate enrollments found. Nothing to clean up.")
        conn.close()
        return
    
    print(f"Found {len(duplicates)} student-year combinations with multiple enrollments.\n")
    print(f"{'DRY RUN' if not args.apply else 'APPLYING CHANGES'}...\n")
    
    total_migrated = {'assessments': 0, 'assessments_deleted': 0, 'interventions': 0, 'notes': 0, 'goals': 0}
    enrollments_to_delete = []
    
    for student_uuid, school_year in duplicates:
        # Get student name for reporting
        cur.execute(
            "SELECT display_name FROM students_core WHERE student_uuid = %s",
            (student_uuid,),
        )
        name_row = cur.fetchone()
        student_name = name_row[0] if name_row else student_uuid[:8]
        
        # Choose enrollment to keep
        keep_enrollment_id = choose_enrollment_to_keep(conn, student_uuid, school_year)
        
        # Get all enrollments for this student-year
        cur.execute(
            """
            SELECT enrollment_id, grade_level, class_name
            FROM student_enrollments
            WHERE student_uuid = %s AND school_year = %s
            """,
            (student_uuid, school_year),
        )
        all_enrollments = cur.fetchall()
        
        kept_enrollment = next((e for e in all_enrollments if e[0] == keep_enrollment_id), None)
        duplicates_to_remove = [e for e in all_enrollments if e[0] != keep_enrollment_id]
        
        if not kept_enrollment:
            print(f"  [WARN] Skipping {student_name} ({school_year}): could not determine enrollment to keep")
            continue
        
        print(f"{student_name} ({school_year}):")
        print(f"  [KEEP] {kept_enrollment[1]} / {kept_enrollment[2]} (enrollment_id: {keep_enrollment_id})")
        
        for dup_eid, dup_grade, dup_class in duplicates_to_remove:
            print(f"  [REMOVE] {dup_grade} / {dup_class} (enrollment_id: {dup_eid})")
            
            # Migrate data
            counts = migrate_data_to_enrollment(conn, dup_eid, keep_enrollment_id, dry_run=not args.apply)
            for key, val in counts.items():
                total_migrated[key] += val
                if val > 0:
                    action = "Deleted" if key == "assessments_deleted" else "Migrated"
                    print(f"    -> {action} {val} {key.replace('_deleted', '').replace('_', ' ')}")
            
            enrollments_to_delete.append(dup_eid)
        
        print()
    
    # Delete duplicate enrollments
    if enrollments_to_delete:
        placeholders = ','.join(['%s'] * len(enrollments_to_delete))
        cur.execute(
            f"""
            DELETE FROM student_enrollments
            WHERE enrollment_id IN ({placeholders})
            """,
            enrollments_to_delete,
        )
        deleted_count = cur.rowcount
        
        if not args.apply:
            conn.rollback()
            print(f"\nWould delete {deleted_count} duplicate enrollment(s).")
        else:
            conn.commit()
            print(f"\n[OK] Deleted {deleted_count} duplicate enrollment(s).")
    
    print(f"\nSummary:")
    print(f"  - Student-year combinations cleaned: {len(duplicates)}")
    print(f"  - Enrollments removed: {len(enrollments_to_delete)}")
    print(f"  - Data migrated:")
    for key, val in total_migrated.items():
        if val > 0:
            print(f"    - {key}: {val}")
    
    if not args.apply:
        print("\nDry run complete. Re-run with --apply to make these changes.")
    
    conn.close()


if __name__ == "__main__":
    main()
