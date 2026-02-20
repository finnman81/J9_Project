#!/usr/bin/env python3
"""
Add upper-grade (5th–8th) sample data.

This script:
- Creates ~20 students per grade for Fifth, Sixth, Seventh, and Eighth.
- Assigns them to 2 classes per grade (10 students per class).
- Adds simple Reading + Math assessments for each new student so they have
  data that looks reasonable in reports.
- Wires those students into the **teacher-first pipeline** by:
  - Creating `students_core` identities + `student_id_map` rows.
  - Creating `student_enrollments` rows for the given year/grade/class.
  - Updating `assessments.enrollment_id` so `v_teacher_roster` / `v_support_status`
    and the Overview dashboards can see the new grades.

Usage (from project root):

    python scripts/add_upper_grade_sample_data.py

Safe to run multiple times; it uses ON CONFLICT to avoid duplicating students
for the same (name, grade_level, school_year).
"""

import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_db_connection  # type: ignore

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


SCHOOL_YEAR = "2024-25"
UPPER_GRADES: List[str] = ["Fifth", "Sixth", "Seventh", "Eighth"]

# Two classes per grade, 10 students per class.
TEACHERS_BY_GRADE: Dict[str, List[Tuple[str, str]]] = {
    "Fifth": [("Ms. Lopez", "5-A"), ("Mr. Green", "5-B")],
    "Sixth": [("Ms. Patel", "6-A"), ("Mr. Johnson", "6-B")],
    "Seventh": [("Mrs. Rivera", "7-A"), ("Mr. Chen", "7-B")],
    "Eighth": [("Ms. Nguyen", "8-A"), ("Mr. Thompson", "8-B")],
}

# Very simple ORF-style ranges for upper grades (words per minute).
READING_RANGES = {
    "Fifth": (95, 165),
    "Sixth": (105, 175),
    "Seventh": (115, 185),
    "Eighth": (125, 195),
}

# Simple Math composite-like ranges (arbitrary points, normalized to 0–100).
MATH_RANGES = {
    "Fifth": (180, 260),
    "Sixth": (190, 270),
    "Seventh": (200, 280),
    "Eighth": (210, 290),
}


def create_upper_grade_students() -> list[tuple[int, str, str]]:
    conn = get_db_connection()
    cur = conn.cursor()

    random.seed(123)
    np.random.seed(123)

    # Find any existing upper-grade students for this year so we don't duplicate.
    cur.execute(
        """
        SELECT student_id, student_name, grade_level
        FROM students
        WHERE school_year = %s AND grade_level = ANY(%s)
        """,
        (SCHOOL_YEAR, UPPER_GRADES),
    )
    existing = {(row[1], row[2]) for row in cur.fetchall()}  # (student_name, grade_level)

    new_students: List[Tuple[int, str, str]] = []  # (student_id, grade_level, student_name)

    for grade in UPPER_GRADES:
        teacher_pairs = TEACHERS_BY_GRADE.get(grade, [("Teacher", f"{grade[:1]}-A"), ("Teacher", f"{grade[:1]}-B")])

        for i in range(20):
            # Example names: "Fifth Student 01", etc.
            name = f"{grade} Student {i+1:02d}"
            if (name, grade) in existing:
                # Already present; look up id and reuse.
                cur.execute(
                    "SELECT student_id FROM students WHERE student_name = %s AND grade_level = %s AND school_year = %s",
                    (name, grade, SCHOOL_YEAR),
                )
                row = cur.fetchone()
                if row:
                    new_students.append((int(row[0]), grade, name))
                continue

            teacher_name, class_name = teacher_pairs[i % len(teacher_pairs)]

            cur.execute(
                """
                INSERT INTO students (student_name, grade_level, class_name, teacher_name, school_year)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (student_name, grade_level, school_year) DO NOTHING
                RETURNING student_id
                """,
                (name, grade, class_name, teacher_name, SCHOOL_YEAR),
            )
            rv = cur.fetchone()
            if rv:
                sid = int(rv[0])
                new_students.append((sid, grade, name))

    conn.commit()
    print(f"Created or reused {len(new_students)} upper-grade students (5th–8th) for {SCHOOL_YEAR}.")

    # Now add simple Reading + Math assessments for each new student.
    periods = ["Fall", "Winter", "Spring"]

    for sid, grade, name in new_students:
        # Reading: ORF-like measure
        r_lo, r_hi = READING_RANGES.get(grade, (80, 160))
        for period in periods:
            score = random.randint(r_lo, r_hi)
            norm = min(100.0, round((score / r_hi) * 100.0, 1))
            cur.execute(
                """
                INSERT INTO assessments
                    (student_id, assessment_type, assessment_period, school_year,
                     score_value, score_normalized, subject_area)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (student_id, assessment_type, assessment_period, school_year) DO NOTHING
                """,
                (sid, "ORF", period, SCHOOL_YEAR, str(score), norm, "Reading"),
            )

        # Math: simple composite-like measure
        m_lo, m_hi = MATH_RANGES.get(grade, (150, 260))
        for period in periods:
            score = random.randint(m_lo, m_hi)
            norm = min(100.0, round((score / m_hi) * 100.0, 1))
            cur.execute(
                """
                INSERT INTO assessments
                    (student_id, assessment_type, assessment_period, school_year,
                     score_value, score_normalized, subject_area)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (student_id, assessment_type, assessment_period, school_year) DO NOTHING
                """,
                (sid, "Math_Composite", period, SCHOOL_YEAR, str(score), norm, "Math"),
            )

    conn.commit()
    conn.close()
    print("Added simple Reading and Math assessments for all new upper-grade students.")
    return new_students


def wire_upper_grades_into_enrollments(students: list[tuple[int, str, str]]) -> None:
    """
    Ensure upper-grade students participate in teacher-first views by:
    - Creating students_core + student_id_map rows where missing.
    - Creating student_enrollments rows.
    - Updating assessments.enrollment_id for their assessments.
    """
    if not students:
        print("No upper-grade students to wire into enrollments.")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    # Load full student records (including class/teacher) for these ids.
    legacy_ids = sorted({sid for (sid, _grade, _name) in students})
    cur.execute(
        """
        SELECT student_id, student_name, grade_level, class_name, teacher_name
        FROM students
        WHERE student_id = ANY(%s) AND school_year = %s
        """,
        (legacy_ids, SCHOOL_YEAR),
    )
    rows = cur.fetchall()
    if not rows:
        print("No matching legacy students found to wire; skipping enrollment wiring.")
        conn.close()
        return

    # Existing mappings legacy_student_id -> student_uuid
    cur.execute(
        """
        SELECT legacy_student_id, student_uuid
        FROM student_id_map
        WHERE legacy_student_id = ANY(%s)
        """,
        (legacy_ids,),
    )
    mapping_rows = cur.fetchall()
    legacy_to_uuid = {int(r[0]): str(r[1]) for r in mapping_rows}

    created_core = 0
    created_enrollments = 0
    updated_assessments = 0

    for student_id, student_name, grade_level, class_name, teacher_name in rows:
        legacy_id = int(student_id)

        # 1) Ensure students_core + mapping
        student_uuid = legacy_to_uuid.get(legacy_id)
        if not student_uuid:
            cur.execute(
                """
                INSERT INTO students_core (display_name, active)
                VALUES (%s, TRUE)
                RETURNING student_uuid
                """,
                (student_name,),
            )
            student_uuid = str(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO student_id_map (legacy_student_id, student_uuid)
                VALUES (%s, %s)
                ON CONFLICT (legacy_student_id) DO NOTHING
                """,
                (legacy_id, student_uuid),
            )
            legacy_to_uuid[legacy_id] = student_uuid
            created_core += 1

        # 2) Ensure an enrollment exists for this uuid/year/grade/class
        cur.execute(
            """
            SELECT enrollment_id
            FROM student_enrollments
            WHERE student_uuid = %s
              AND school_year = %s
              AND grade_level = %s
              AND class_name = %s
            LIMIT 1
            """,
            (student_uuid, SCHOOL_YEAR, grade_level, class_name),
        )
        row_e = cur.fetchone()
        if row_e:
            enrollment_id = row_e[0]
        else:
            cur.execute(
                """
                INSERT INTO student_enrollments (student_uuid, school_year, grade_level, class_name, teacher_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING enrollment_id
                """,
                (student_uuid, SCHOOL_YEAR, grade_level, class_name, teacher_name),
            )
            enrollment_id = cur.fetchone()[0]
            created_enrollments += 1

        # 3) Attach this enrollment_id to any of the student's assessments for this year
        cur.execute(
            """
            UPDATE assessments
            SET enrollment_id = %s
            WHERE student_id = %s
              AND school_year = %s
              AND enrollment_id IS NULL
            """,
            (enrollment_id, legacy_id, SCHOOL_YEAR),
        )
        updated_assessments += cur.rowcount

    conn.commit()
    conn.close()

    print(
        f"Wired upper grades into teacher-first views: "
        f"{created_core} students_core row(s), "
        f"{created_enrollments} enrollment(s), "
        f"{updated_assessments} assessment row(s) updated."
    )


def main():
    students = create_upper_grade_students()
    wire_upper_grades_into_enrollments(students)


if __name__ == "__main__":
    main()

