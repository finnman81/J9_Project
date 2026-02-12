"""
Generate sample data to fill gaps in the database (batch version).
Run once:  python generate_sample_data.py
"""
import random, sys
import numpy as np
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_connection
import pandas as pd

random.seed(42)
np.random.seed(42)

conn = get_db_connection()
cur = conn.cursor()

# ---------------------------------------------------------------------------
# Read existing data
# ---------------------------------------------------------------------------
students = pd.read_sql_query("SELECT student_id, student_name, grade_level, class_name, teacher_name FROM students", conn)
lit_scores = pd.read_sql_query(
    """SELECT ls.student_id, ls.risk_level, ls.overall_literacy_score
       FROM literacy_scores ls
       WHERE ls.score_id = (
           SELECT score_id FROM literacy_scores ls2
           WHERE ls2.student_id = ls.student_id
           ORDER BY ls2.calculated_at DESC LIMIT 1)""", conn)
at_risk = lit_scores[lit_scores['risk_level'].isin(['High', 'Medium'])]

print(f"Found {len(students)} students, {len(at_risk)} at-risk")

# ---------------------------------------------------------------------------
# 1. Fill missing teacher/class assignments
# ---------------------------------------------------------------------------
TEACHERS = {
    'Kindergarten': [('Mrs. Johnson', 'K-A'), ('Mrs. Garcia', 'K-B')],
    'First':        [('Mrs. Smith', '1-A'), ('Mr. Davis', '1-B')],
    'Second':       [('Mrs. Lee', '2-A'), ('Ms. Williams', '2-B')],
    'Third':        [('Mr. Brown', '3-A'), ('Mrs. Taylor', '3-B')],
    'Fourth':       [('Mrs. Martinez', '4-A'), ('Mr. Wilson', '4-B')],
}
missing = students[(students['class_name'].isna()) | (students['teacher_name'].isna())]
for _, row in missing.iterrows():
    opts = TEACHERS.get(row['grade_level'], [('Teacher', 'Class')])
    t, c = random.choice(opts)
    cur.execute("UPDATE students SET teacher_name=%s, class_name=%s WHERE student_id=%s",
                (t, c, int(row['student_id'])))
conn.commit()
print(f"1. Updated {len(missing)} students with teacher/class")

# ---------------------------------------------------------------------------
# 2. Interventions
# ---------------------------------------------------------------------------
INTERVENTION_TYPES = [
    ('Guided Reading', '3x/week', 20),
    ('Phonics Intervention', '4x/week', 15),
    ('Fluency Practice', '5x/week', 10),
    ('Sight Word Drill', '3x/week', 10),
    ('Reading Recovery', '5x/week', 30),
    ('Lexia Core5', 'Daily', 20),
    ('Wilson Reading', '4x/week', 25),
    ('Decodable Readers', '3x/week', 15),
]
NOTES = [
    'Showing steady progress.', 'Needs consistent attendance.',
    'Responding well to small group.', 'Parent informed of support plan.',
    'Re-evaluate at next benchmark window.', None,
]
interv_rows = []
for _, row in at_risk.iterrows():
    if random.random() < 0.70:
        itype, freq, dur = random.choice(INTERVENTION_TYPES)
        start = date(2024, 9, random.randint(3, 20))
        status = random.choice(['Active'] * 8 + ['Completed', 'Paused'])
        end = start + timedelta(days=random.randint(60, 180)) if status == 'Completed' else None
        interv_rows.append((int(row['student_id']), itype, start, end, freq, dur, status, random.choice(NOTES)))

if interv_rows:
    from psycopg2.extras import execute_values
    execute_values(cur,
        """INSERT INTO interventions (student_id, intervention_type, start_date, end_date,
               frequency, duration_minutes, status, notes)
           VALUES %s ON CONFLICT DO NOTHING""",
        interv_rows)
    conn.commit()
print(f"2. Created {len(interv_rows)} interventions")

# ---------------------------------------------------------------------------
# 3. Acadience measures
# ---------------------------------------------------------------------------
ACADIENCE_RANGES = {
    'Kindergarten': {
        'FSF':     {'Fall': (15, 55), 'Winter': (30, 65), 'Spring': (40, 75)},
        'LNF':     {'Fall': (10, 45), 'Winter': (25, 55), 'Spring': (35, 65)},
        'PSF':     {'Fall': (5, 30),  'Winter': (20, 50), 'Spring': (30, 60)},
        'NWF-CLS': {'Fall': (5, 25),  'Winter': (15, 45), 'Spring': (25, 60)},
    },
    'First': {
        'LNF':     {'Fall': (30, 60), 'Winter': (40, 65), 'Spring': (45, 70)},
        'PSF':     {'Fall': (25, 55), 'Winter': (35, 65), 'Spring': (45, 65)},
        'NWF-CLS': {'Fall': (20, 55), 'Winter': (35, 75), 'Spring': (50, 95)},
        'NWF-WWR': {'Fall': (2, 12),  'Winter': (5, 20),  'Spring': (8, 30)},
        'ORF':     {'Winter': (10, 50), 'Spring': (20, 70)},
    },
    'Second': {
        'NWF-CLS': {'Fall': (40, 90), 'Winter': (50, 105), 'Spring': (60, 115)},
        'ORF':     {'Fall': (30, 85), 'Winter': (50, 110), 'Spring': (65, 125)},
        'Retell':  {'Fall': (10, 35), 'Winter': (15, 45),  'Spring': (18, 50)},
    },
    'Third': {
        'ORF':     {'Fall': (50, 120), 'Winter': (70, 140), 'Spring': (80, 155)},
        'Retell':  {'Fall': (15, 45),  'Winter': (20, 55),  'Spring': (25, 60)},
        'Maze':    {'Fall': (5, 18),   'Winter': (8, 22),   'Spring': (10, 28)},
    },
    'Fourth': {
        'ORF':     {'Fall': (70, 145), 'Winter': (85, 160), 'Spring': (95, 170)},
        'Retell':  {'Fall': (18, 50),  'Winter': (22, 55),  'Spring': (25, 60)},
        'Maze':    {'Fall': (8, 22),   'Winter': (12, 28),  'Spring': (15, 32)},
    },
}

acad_rows = []
for _, stu in students.iterrows():
    grade = stu['grade_level']
    sid = int(stu['student_id'])
    measures = ACADIENCE_RANGES.get(grade, {})
    ability = max(0.05, min(0.95, np.random.normal(0.5, 0.22)))

    for measure, period_ranges in measures.items():
        for period in ['Fall', 'Winter', 'Spring']:
            if period not in period_ranges:
                continue
            lo, hi = period_ranges[period]
            score = max(0, int(lo + (hi - lo) * ability + np.random.normal(0, (hi - lo) * 0.08)))
            norm = min(100.0, max(0.0, (score - lo) / max(1, hi - lo) * 100))
            acad_rows.append((sid, measure, period, '2024-25', str(score), round(norm, 1)))

if acad_rows:
    from psycopg2.extras import execute_values
    execute_values(cur,
        """INSERT INTO assessments (student_id, assessment_type, assessment_period,
               school_year, score_value, score_normalized)
           VALUES %s ON CONFLICT (student_id, assessment_type, assessment_period, school_year)
           DO NOTHING""",
        acad_rows)
    conn.commit()
print(f"3. Created {len(acad_rows)} Acadience assessment rows")

# ---------------------------------------------------------------------------
# 4. ERB / CTP5 subtest scores
# ---------------------------------------------------------------------------
# Use same subtest keys as erb_scoring.ERB_SUBTESTS (canonical format with colons)
ERB_SUBTESTS = [
    'ERB_Reading_Comp', 'ERB_Vocabulary', 'ERB_Writing_Mechanics',
    'ERB_Writing_Concepts', 'ERB_Mathematics',
    'ERB_Verbal_Reasoning', 'ERB_Quant_Reasoning',
]
STANINE_PCT_MID = {1: 4, 2: 11, 3: 23, 4: 40, 5: 50, 6: 60, 7: 77, 8: 89, 9: 96}

erb_rows = []
erb_students = students[students['grade_level'].isin(['First', 'Second', 'Third', 'Fourth'])]
for _, stu in erb_students.iterrows():
    sid = int(stu['student_id'])
    ability = max(1, min(9, np.random.normal(5.5, 2.0)))

    for subtest in ERB_SUBTESTS:
        stanine = int(np.clip(round(ability + np.random.normal(0, 0.9)), 1, 9))
        pct_mid = STANINE_PCT_MID[stanine]
        percentile = int(np.clip(pct_mid + np.random.randint(-6, 7), 1, 99))
        scale_score = int(400 + stanine * 30 + np.random.randint(-15, 16))
        growth_pct = int(np.clip(np.random.normal(50, 18), 1, 99))
        # Canonical format (colons) for erb_scoring.parse_erb_score_value
        sv = f"stanine:{stanine}|percentile:{percentile}|scale:{scale_score}|growth:{growth_pct}"
        erb_rows.append((sid, subtest, 'Spring', '2024-25', sv, round(float(percentile), 1)))

if erb_rows:
    from psycopg2.extras import execute_values
    execute_values(cur,
        """INSERT INTO assessments (student_id, assessment_type, assessment_period,
               school_year, score_value, score_normalized)
           VALUES %s ON CONFLICT (student_id, assessment_type, assessment_period, school_year)
           DO NOTHING""",
        erb_rows)
    conn.commit()
print(f"4. Created {len(erb_rows)} ERB assessment rows")

# ---------------------------------------------------------------------------
# 5. Student goals
# ---------------------------------------------------------------------------
goal_rows = []
at_risk_with_scores = at_risk[at_risk['overall_literacy_score'].notna()]
for _, row in at_risk_with_scores.iterrows():
    if random.random() < 0.5:
        continue
    m = random.choice(['Composite', 'ORF', 'NWF-CLS'])
    baseline = float(row['overall_literacy_score'])
    target = round(baseline + random.uniform(8, 20), 1)
    weekly = round(random.uniform(0.5, 2.0), 2)
    goal_rows.append((int(row['student_id']), m, baseline, target, weekly,
                       date(2024, 9, 9), date(2025, 5, 30)))

if goal_rows:
    from psycopg2.extras import execute_values
    execute_values(cur,
        """INSERT INTO student_goals (student_id, measure, baseline_score, target_score,
               expected_weekly_growth, start_date, target_date)
           VALUES %s ON CONFLICT DO NOTHING""",
        goal_rows)
    conn.commit()
print(f"5. Created {len(goal_rows)} student goals")

# ---------------------------------------------------------------------------
# 6. Teacher notes
# ---------------------------------------------------------------------------
NOTE_TEMPLATES = [
    ("Showed strong improvement in fluency this week.", "Progress"),
    ("Struggles with CVC blending — needs more phonics support.", "Concern"),
    ("Parent conference held; agreed on daily reading at home.", "Parent Contact"),
    ("Moved to Tier 2 small group for decoding.", "Intervention"),
    ("Exceeded ORF benchmark — great progress!", "Progress"),
    ("Absent 3 days this month; missed guided reading sessions.", "Attendance"),
    ("Enjoys reading independently during free time.", "Observation"),
    ("Needs extra time with multisyllabic words.", "Concern"),
    ("Re-assessed with winter benchmark; improved 12 points.", "Assessment"),
    ("Working on sight word fluency with flash cards.", "Intervention"),
]
note_rows = []
for _, stu in students.iterrows():
    if random.random() < 0.40:
        for _ in range(random.randint(1, 3)):
            text, tag = random.choice(NOTE_TEMPLATES)
            nd = date(2024, 9, 1) + timedelta(days=random.randint(0, 150))
            teacher = stu['teacher_name'] or 'Teacher'
            note_rows.append((int(stu['student_id']), text, tag, nd, teacher))

if note_rows:
    from psycopg2.extras import execute_values
    execute_values(cur,
        """INSERT INTO teacher_notes (student_id, note_text, tag, note_date, created_by)
           VALUES %s""",
        note_rows)
    conn.commit()
print(f"6. Created {len(note_rows)} teacher notes")

# ---------------------------------------------------------------------------
# 7. Back-fill trend column in literacy_scores
# ---------------------------------------------------------------------------
cur.execute("""
    WITH ordered AS (
        SELECT score_id, student_id, overall_literacy_score,
               LAG(overall_literacy_score) OVER (
                   PARTITION BY student_id ORDER BY school_year,
                   CASE assessment_period
                       WHEN 'Fall' THEN 1 WHEN 'Winter' THEN 2
                       WHEN 'Spring' THEN 3 WHEN 'EOY' THEN 4 ELSE 0 END,
                   calculated_at
               ) AS prev_score
        FROM literacy_scores
    )
    UPDATE literacy_scores ls SET trend =
        CASE
            WHEN o.prev_score IS NULL THEN 'New'
            WHEN ls.overall_literacy_score > o.prev_score + 2 THEN 'Improving'
            WHEN ls.overall_literacy_score < o.prev_score - 2 THEN 'Declining'
            ELSE 'Stable'
        END
    FROM ordered o WHERE o.score_id = ls.score_id
""")
conn.commit()
print("7. Trends back-filled")

conn.close()
print("\nDone! All sample data generated.")
