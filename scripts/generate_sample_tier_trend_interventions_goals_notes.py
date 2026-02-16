#!/usr/bin/env python3
"""
Generate sample data for all students so Student Detail shows:
- Tier / Risk (via benchmark_thresholds so v_support_status can compute tier)
- Trend (ensure 2+ assessments per enrollment/subject/year so v_growth_last_two has trend)
- Sample interventions for at-risk enrollments (Intensive/Strategic)
- Sample goals per enrollment
- Sample notes per enrollment

Run once: python scripts/generate_sample_tier_trend_interventions_goals_notes.py
"""
import os
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()

    # -------------------------------------------------------------------------
    # 1. Benchmark thresholds (so v_support_status shows Tier: Core/Strategic/Intensive)
    # -------------------------------------------------------------------------
    cur.execute("""
        SELECT DISTINCT a.subject_area, a.assessment_type, e.grade_level, a.assessment_period, a.school_year
        FROM assessments a
        JOIN student_enrollments e ON e.enrollment_id = a.enrollment_id
        WHERE a.enrollment_id IS NOT NULL
    """)
    rows = cur.fetchall()
    # Support = below this is Intensive; Benchmark = below this is Strategic; above = Core
    support_pct, benchmark_pct = 40, 70
    seen = set()
    threshold_rows = []
    for (subj, atype, grade, period, year) in rows:
        key = (subj, atype, grade, period, year)
        if key in seen:
            continue
        seen.add(key)
        threshold_rows.append((subj, atype, grade, period, year, float(support_pct), float(benchmark_pct)))
    if threshold_rows:
        cur.execute("SELECT 1 FROM benchmark_thresholds LIMIT 1")
        if cur.fetchone() is None:
            execute_values(cur, """
                INSERT INTO benchmark_thresholds (subject_area, assessment_type, grade_level, assessment_period, school_year, support_threshold, benchmark_threshold)
                VALUES %s
            """, threshold_rows)
            conn.commit()
            print(f"1. Seeded {len(threshold_rows)} benchmark_thresholds (Tier/Risk will now show Core/Strategic/Intensive where matched).")
        else:
            print("1. benchmark_thresholds already has data; skipping.")
    else:
        print("1. No assessment+enrollment combinations found; skipping benchmark_thresholds.")

    # -------------------------------------------------------------------------
    # 2. Second assessment per (enrollment, subject, year) where missing (for Trend)
    # -------------------------------------------------------------------------
    cur.execute("""
        WITH one_per AS (
            SELECT a.enrollment_id, a.subject_area, a.school_year, COUNT(*) AS cnt
            FROM assessments a
            WHERE a.enrollment_id IS NOT NULL AND a.score_normalized IS NOT NULL
            GROUP BY a.enrollment_id, a.subject_area, a.school_year
            HAVING COUNT(*) = 1
        ),
        single_assess AS (
            SELECT a.enrollment_id, a.subject_area, a.school_year, a.assessment_type, a.assessment_period,
                   a.student_id, a.effective_date, a.score_normalized
            FROM assessments a
            JOIN one_per o ON o.enrollment_id = a.enrollment_id AND o.subject_area = a.subject_area AND o.school_year = a.school_year
            WHERE a.enrollment_id IS NOT NULL AND a.score_normalized IS NOT NULL
        )
        SELECT enrollment_id, subject_area, school_year, assessment_type, assessment_period, student_id, effective_date, score_normalized
        FROM single_assess
    """)
    singles = cur.fetchall()
    period_before = {"Winter": "Fall", "Spring": "Winter", "EOY": "Spring", "Fall": None}
    added_trend = 0
    for (eid, subj, year, atype, current_period, sid, eff_date, score) in singles:
        prior_period = period_before.get(current_period) if current_period else "Fall"
        if not prior_period:
            continue
        if eff_date is None:
            eff_date = date(2024, 10, 1)
        y = eff_date.year if hasattr(eff_date, 'year') else int(str(eff_date)[:4])
        if prior_period == "Fall":
            prior_date = date(y, 10, 15)
        elif prior_period == "Winter":
            prior_date = date(y + 1, 1, 15)
        else:
            prior_date = date(y + 1, 3, 15)
        prior_score = max(0, (score - random.uniform(2, 8)) if isinstance(score, (int, float)) else 50)
        try:
            cur.execute("""
                INSERT INTO assessments (student_id, enrollment_id, subject_area, assessment_type, assessment_period, school_year, score_normalized, effective_date, assessment_date, entered_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'sample_trend')
            """, (sid, eid, subj, atype, prior_period, year, prior_score, prior_date, prior_date))
            if cur.rowcount:
                added_trend += 1
        except Exception:
            pass
    conn.commit()
    print(f"2. Added {added_trend} prior assessments so Trend can show (Improving/Stable/Declining).")

    # -------------------------------------------------------------------------
    # 3. At-risk enrollments: add interventions (query v_support_status after thresholds exist)
    # -------------------------------------------------------------------------
    cur.execute("""
        SELECT ss.enrollment_id, ss.subject_area, ss.display_name
        FROM v_support_status ss
        WHERE ss.tier IN ('Intensive', 'Strategic')
    """)
    at_risk = cur.fetchall()
    cur.execute("""
        SELECT e.enrollment_id, (SELECT m.legacy_student_id FROM student_id_map m WHERE m.student_uuid = e.student_uuid ORDER BY m.legacy_student_id LIMIT 1) AS legacy_student_id
        FROM student_enrollments e
    """)
    eid_to_sid = {str(r[0]): r[1] for r in cur.fetchall() if r[1] is not None}
    INTERVENTION_TYPES_READING = [
        ("Guided Reading", "3x/week", 20), ("Phonics Intervention", "4x/week", 15),
        ("Sight Word Drill", "3x/week", 15), ("Decodable Readers", "4x/week", 20),
    ]
    INTERVENTION_TYPES_MATH = [
        ("Math Tutoring", "3x/week", 25), ("Number Fluency Practice", "4x/week", 15),
        ("Small Group Math", "3x/week", 20),
    ]
    existing_int = set()
    cur.execute("SELECT enrollment_id, subject_area, intervention_type FROM interventions WHERE enrollment_id IS NOT NULL")
    for r in cur.fetchall():
        existing_int.add((str(r[0]), r[1], r[2]))
    int_rows = []
    for (eid, subj, _) in at_risk:
        sid = eid_to_sid.get(str(eid))
        if not sid:
            continue
        pool = INTERVENTION_TYPES_READING if subj == "Reading" else INTERVENTION_TYPES_MATH
        itype, freq, dur = random.choice(pool)
        if (str(eid), subj, itype) in existing_int:
            continue
        start = date(2024, 9, random.randint(1, 20))
        int_rows.append((int(sid), str(eid), subj, itype, start, freq, dur, "Active", "Sample intervention for at-risk student."))
        existing_int.add((str(eid), subj, itype))
    if int_rows:
        execute_values(cur, """
            INSERT INTO interventions (student_id, enrollment_id, subject_area, intervention_type, start_date, frequency, duration_minutes, status, notes)
            VALUES %s
        """, int_rows)
        conn.commit()
        print(f"3. Inserted {len(int_rows)} interventions for at-risk enrollments.")
    else:
        print("3. No new interventions to add (none at-risk or already present).")

    # -------------------------------------------------------------------------
    # 4. Sample goals (one per enrollment, subject Reading or Math)
    # -------------------------------------------------------------------------
    cur.execute("""
        SELECT e.enrollment_id,
               (SELECT m.legacy_student_id FROM student_id_map m WHERE m.student_uuid = e.student_uuid ORDER BY m.legacy_student_id LIMIT 1) AS legacy_student_id,
               e.school_year
        FROM student_enrollments e
        WHERE NOT EXISTS (SELECT 1 FROM student_goals g WHERE g.enrollment_id = e.enrollment_id)
    """)
    enrollments_no_goal = cur.fetchall()
    MEASURES_READING = ["ORF", "NWF-CLS", "Composite", "Reading_Level"]
    MEASURES_MATH = ["Math_Composite", "Computation", "Concepts"]
    goal_rows = []
    for (eid, sid, year) in enrollments_no_goal:
        if not sid:
            continue
        subj = random.choice(["Reading", "Math"])
        measure = random.choice(MEASURES_READING if subj == "Reading" else MEASURES_MATH)
        baseline = round(random.uniform(35, 65), 1)
        target = round(baseline + random.uniform(15, 30), 1)
        weekly = round(random.uniform(0.5, 2.0), 2)
        start_d = date(2024, 9, 1)
        end_d = date(2025, 5, 30)
        goal_rows.append((int(sid), str(eid), measure, baseline, target, weekly, start_d, end_d))
    if goal_rows:
        execute_values(cur, """
            INSERT INTO student_goals (student_id, enrollment_id, measure, baseline_score, target_score, expected_weekly_growth, start_date, target_date)
            VALUES %s
        """, goal_rows)
        conn.commit()
        print(f"4. Inserted {len(goal_rows)} sample goals.")
    else:
        print("4. No enrollments without goals to add (or limit reached).")

    # -------------------------------------------------------------------------
    # 5. Sample notes (one per enrollment)
    # -------------------------------------------------------------------------
    cur.execute("""
        SELECT e.enrollment_id,
               (SELECT m.legacy_student_id FROM student_id_map m WHERE m.student_uuid = e.student_uuid ORDER BY m.legacy_student_id LIMIT 1) AS legacy_student_id
        FROM student_enrollments e
        WHERE NOT EXISTS (SELECT 1 FROM teacher_notes n WHERE n.enrollment_id = e.enrollment_id)
    """)
    enrollments_no_note = cur.fetchall()
    NOTE_TEMPLATES = [
        "Student is making progress. Will continue to monitor.",
        "Parent conference scheduled. Goals reviewed.",
        "Participating well in small group instruction.",
        "Focus on fluency this month.",
        "Completed mid-year benchmark. On track.",
    ]
    note_rows = []
    for (eid, sid) in enrollments_no_note:
        if not sid:
            continue
        note_text = random.choice(NOTE_TEMPLATES)
        note_date = date(2024, random.randint(9, 12), random.randint(1, 28))
        note_rows.append((int(sid), str(eid), note_text, "general", note_date, "Teacher"))
    if note_rows:
        execute_values(cur, """
            INSERT INTO teacher_notes (student_id, enrollment_id, note_text, tag, note_date, created_by)
            VALUES %s
        """, note_rows)
        conn.commit()
        print(f"5. Inserted {len(note_rows)} sample notes.")
    else:
        print("5. No enrollments without notes to add.")

    conn.close()
    print("Done. Reload Student Detail pages to see Tier/Risk, Trend, interventions, goals, and notes.")


if __name__ == "__main__":
    main()
