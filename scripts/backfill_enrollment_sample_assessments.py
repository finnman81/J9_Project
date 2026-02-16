#!/usr/bin/env python3
"""
Backfill one Reading and one Math assessment per enrollment that currently has
no assessments. Picks (assessment_type, period) not already used for that
student_id/school_year to satisfy the legacy unique constraint.
"""
import os
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

READING_SLOTS = [
    ("Benchmark", "Fall"), ("Sight_Words", "Winter"), ("NWF_CLS", "Spring"),
    ("LNF", "Fall"), ("PSF", "Winter"), ("MNF", "Spring"),
    ("ORF", "Fall"), ("Decodable_Level", "Winter"), ("NWF_WWR", "Fall"),
]
MATH_SLOTS = [
    ("Math_Composite", "Fall"), ("NIF", "Winter"), ("NNF", "Spring"),
    ("Computation", "Fall"), ("Concepts", "Winter"), ("ERB_Mathematics", "Spring"),
]


def period_to_date(period: str, school_year: str) -> date:
    year_part = (school_year or "2024").split("-")[0]
    y = int(year_part)
    if period == "Fall":
        return date(y, 10, 15)
    if period == "Winter":
        return date(y + 1, 1, 15)
    if period == "Spring":
        return date(y + 1, 3, 15)
    return date(y, 10, 1)


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()

    # Enrollments with no assessments; one legacy_student_id per enrollment
    cur.execute("""
        WITH no_assess AS (
            SELECT e.enrollment_id, e.student_uuid, e.school_year,
                   (SELECT m.legacy_student_id FROM student_id_map m
                    WHERE m.student_uuid = e.student_uuid
                    ORDER BY m.legacy_student_id LIMIT 1) AS legacy_student_id
            FROM student_enrollments e
            WHERE NOT EXISTS (
                SELECT 1 FROM assessments a WHERE a.enrollment_id = e.enrollment_id
            )
        )
        SELECT enrollment_id, legacy_student_id, COALESCE(school_year, '2024-25')
        FROM no_assess
        WHERE legacy_student_id IS NOT NULL
        ORDER BY enrollment_id
        LIMIT 1000
    """)
    rows = cur.fetchall()

    if not rows:
        print("No enrollments without assessments; nothing to backfill.")
        conn.close()
        return

    # Existing (student_id, assessment_type, assessment_period, school_year) for these students
    student_ids = list({r[1] for r in rows})
    placeholders = ",".join(["%s"] * len(student_ids))
    cur.execute(
        f"""SELECT student_id, assessment_type, assessment_period, school_year
            FROM assessments
            WHERE student_id IN ({placeholders})""",
        student_ids,
    )
    used = set(cur.fetchall())

    inserted = 0
    max_slot_tries = max(len(READING_SLOTS), len(MATH_SLOTS)) * 2
    for i, (enrollment_id, legacy_student_id, school_year) in enumerate(rows):
        r_type, r_period = READING_SLOTS[i % len(READING_SLOTS)]
        m_type, m_period = MATH_SLOTS[i % len(MATH_SLOTS)]
        slot_idx = i
        for _ in range(max_slot_tries):
            if (legacy_student_id, r_type, r_period, school_year) not in used:
                break
            slot_idx += 1
            r_type, r_period = READING_SLOTS[slot_idx % len(READING_SLOTS)]
        else:
            continue  # no free Reading slot
        used.add((legacy_student_id, r_type, r_period, school_year))
        for _ in range(max_slot_tries):
            if (legacy_student_id, m_type, m_period, school_year) not in used:
                break
            slot_idx += 1
            m_type, m_period = MATH_SLOTS[slot_idx % len(MATH_SLOTS)]
        else:
            used.discard((legacy_student_id, r_type, r_period, school_year))
            continue  # no free Math slot
        used.add((legacy_student_id, m_type, m_period, school_year))

        r_date = period_to_date(r_period, school_year)
        m_date = period_to_date(m_period, school_year)
        r_score = 50.0 + (i % 26)
        m_score = 52.0 + (i % 24)

        for subject_area, assessment_type, assessment_period, eff_date, score in [
            ("Reading", r_type, r_period, r_date, r_score),
            ("Math", m_type, m_period, m_date, m_score),
        ]:
            try:
                cur.execute("""
                    INSERT INTO assessments
                        (student_id, enrollment_id, subject_area, assessment_type,
                         assessment_period, school_year, score_normalized,
                         effective_date, assessment_date, entered_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'backfill')
                """, (
                    legacy_student_id, enrollment_id, subject_area, assessment_type,
                    assessment_period, school_year, score, eff_date, eff_date,
                ))
                inserted += 1
            except Exception as e:
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    # Conflict on (student_id, type, period, year); skip and remember
                    used.add((legacy_student_id, assessment_type, assessment_period, school_year))
                    conn.rollback()
                    cur = conn.cursor()
                else:
                    print(f"Skip {enrollment_id} {subject_area} {assessment_type}: {e}")
                    conn.rollback()
                    cur = conn.cursor()
                continue

    conn.commit()
    conn.close()
    print(f"Backfill complete: {len(rows)} enrollments, {inserted} assessment rows inserted/updated.")


if __name__ == "__main__":
    main()
