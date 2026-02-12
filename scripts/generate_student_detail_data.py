"""
Generate additional sample data to fill out student detail views:
- Reading_Level progression for all students
- Acadience-measure-specific goals for at-risk students
- Ensure all Intensive-tier students have interventions
- Extra teacher notes for demo students
Run once: python generate_student_detail_data.py
"""
import random
import numpy as np
from datetime import date, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_connection
from psycopg2.extras import execute_values
import pandas as pd

random.seed(77)
np.random.seed(77)

conn = get_db_connection()
cur = conn.cursor()

# ---------------------------------------------------------------------------
# Read existing data
# ---------------------------------------------------------------------------
students = pd.read_sql_query(
    "SELECT student_id, student_name, grade_level, school_year FROM students "
    "WHERE school_year = '2024-25'", conn)

lit_scores = pd.read_sql_query("""
    SELECT ls.student_id, ls.risk_level, ls.overall_literacy_score, s.student_name
    FROM literacy_scores ls JOIN students s ON ls.student_id = s.student_id
    WHERE s.school_year = '2024-25'
      AND ls.score_id = (
          SELECT score_id FROM literacy_scores ls2
          WHERE ls2.student_id = ls.student_id
          ORDER BY ls2.calculated_at DESC LIMIT 1)
""", conn)

existing_interventions = pd.read_sql_query(
    "SELECT DISTINCT student_id FROM interventions WHERE status = 'Active'", conn)

existing_goals = pd.read_sql_query(
    "SELECT DISTINCT student_id FROM student_goals", conn)

print(f"Students: {len(students)}, Lit scores: {len(lit_scores)}")

# ---------------------------------------------------------------------------
# 1. Reading_Level progression
# ---------------------------------------------------------------------------
READING_LEVELS_BY_GRADE = {
    'Kindergarten': {'Fall': ['AA', 'A'], 'Winter': ['A', 'B', 'C'], 'Spring': ['B', 'C', 'D']},
    'First':        {'Fall': ['C', 'D', 'E'], 'Winter': ['E', 'F', 'G', 'H'], 'Spring': ['G', 'H', 'I', 'J']},
    'Second':       {'Fall': ['H', 'I', 'J'], 'Winter': ['J', 'K', 'L'], 'Spring': ['L', 'M', 'N']},
    'Third':        {'Fall': ['L', 'M', 'N'], 'Winter': ['N', 'O', 'P'], 'Spring': ['P', 'Q', 'R']},
    'Fourth':       {'Fall': ['P', 'Q', 'R'], 'Winter': ['R', 'S'], 'Spring': ['S', 'T']},
}
LEVEL_ORDER = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
               'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']

reading_rows = []
for _, stu in students.iterrows():
    grade = stu['grade_level']
    sid = int(stu['student_id'])
    levels = READING_LEVELS_BY_GRADE.get(grade, {})
    if not levels:
        continue

    # Student ability determines where in the range they fall
    ability = random.random()
    prev_level_idx = 0

    for period in ['Fall', 'Winter', 'Spring']:
        options = levels.get(period, [])
        if not options:
            continue
        # Pick level based on ability (higher ability = higher level)
        idx = min(int(ability * len(options)), len(options) - 1)
        level = options[idx]
        level_idx = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0
        # Ensure non-decreasing
        level_idx = max(level_idx, prev_level_idx)
        level = LEVEL_ORDER[min(level_idx, len(LEVEL_ORDER) - 1)]
        prev_level_idx = level_idx

        norm = min(100.0, (level_idx / 20.0) * 100)
        reading_rows.append((sid, 'Reading_Level', period, '2024-25', level, round(norm, 1)))

if reading_rows:
    execute_values(cur,
        """INSERT INTO assessments (student_id, assessment_type, assessment_period,
               school_year, score_value, score_normalized)
           VALUES %s
           ON CONFLICT (student_id, assessment_type, assessment_period, school_year) DO NOTHING""",
        reading_rows)
    conn.commit()
print(f"1. Created {len(reading_rows)} Reading_Level entries")

# ---------------------------------------------------------------------------
# 2. Acadience-measure-specific goals for at-risk students without goals
# ---------------------------------------------------------------------------
at_risk = lit_scores[lit_scores['risk_level'].isin(['High', 'Medium'])]
at_risk_no_goal = at_risk[~at_risk['student_id'].isin(existing_goals['student_id'].tolist())]

goal_rows = []
for _, row in at_risk_no_goal.iterrows():
    sid = int(row['student_id'])
    baseline = float(row['overall_literacy_score']) if pd.notna(row['overall_literacy_score']) else 50.0
    measure = random.choice(['Composite', 'ORF', 'NWF-CLS'])
    target = round(baseline + random.uniform(10, 25), 1)
    weekly = round(random.uniform(0.5, 2.0), 2)
    goal_rows.append((sid, measure, baseline, target, weekly,
                       date(2024, 9, 9), date(2025, 5, 30)))

if goal_rows:
    execute_values(cur,
        """INSERT INTO student_goals (student_id, measure, baseline_score, target_score,
               expected_weekly_growth, start_date, target_date)
           VALUES %s ON CONFLICT DO NOTHING""",
        goal_rows)
    conn.commit()
print(f"2. Created {len(goal_rows)} goals for at-risk students")

# ---------------------------------------------------------------------------
# 3. Ensure all Intensive-tier (High risk) students have an intervention
# ---------------------------------------------------------------------------
high_risk = lit_scores[lit_scores['risk_level'] == 'High']
high_no_intervention = high_risk[~high_risk['student_id'].isin(
    existing_interventions['student_id'].tolist())]

INTERVENTION_TYPES = [
    ('Guided Reading', '3x/week', 20),
    ('Phonics Intervention', '4x/week', 15),
    ('Reading Recovery', '5x/week', 30),
    ('Wilson Reading', '4x/week', 25),
    ('Lexia Core5', 'Daily', 20),
]
int_rows = []
for _, row in high_no_intervention.iterrows():
    itype, freq, dur = random.choice(INTERVENTION_TYPES)
    start = date(2024, 9, random.randint(3, 20))
    notes = random.choice([
        'Showing steady progress.', 'Needs consistent attendance.',
        'Responding well to small group.', 'Re-evaluate at next benchmark.',
    ])
    int_rows.append((int(row['student_id']), itype, start, None, freq, dur, 'Active', notes))

if int_rows:
    execute_values(cur,
        """INSERT INTO interventions (student_id, intervention_type, start_date, end_date,
               frequency, duration_minutes, status, notes)
           VALUES %s ON CONFLICT DO NOTHING""",
        int_rows)
    conn.commit()
print(f"3. Created {len(int_rows)} interventions for high-risk students")

# ---------------------------------------------------------------------------
# 4. Extra teacher notes for demo students
# ---------------------------------------------------------------------------
DEMO_NOTES = [
    ("Great improvement on sight words this week!", "Progress"),
    ("Struggling with multisyllabic decoding.", "Concern"),
    ("Parent conference: agreed on nightly reading routine.", "Parent Contact"),
    ("Moved to Tier 2 for fluency support.", "Intervention"),
    ("Exceeded ORF benchmark -- celebrate!", "Progress"),
    ("Needs extra time during independent reading.", "Observation"),
    ("Absent 2 days; missed guided reading group.", "Attendance"),
    ("Retested NWF: improved from 23 to 41 CLS.", "Assessment"),
    ("Using decodable readers at level D.", "Intervention"),
    ("Strong comprehension skills during read-aloud.", "Progress"),
]

# Target demo students and any student with < 2 notes
existing_notes = pd.read_sql_query(
    "SELECT student_id, COUNT(*) as n FROM teacher_notes GROUP BY student_id", conn)
note_counts = dict(zip(existing_notes['student_id'], existing_notes['n']))

note_rows = []
for _, stu in students.iterrows():
    sid = int(stu['student_id'])
    current_count = note_counts.get(sid, 0)
    # Give AJ and other demo students 4-5 notes
    if stu['student_name'] in ('AJ', 'Ada', 'Aiden', 'Alexander'):
        needed = max(0, 5 - current_count)
    elif current_count < 1 and random.random() < 0.3:
        needed = random.randint(1, 2)
    else:
        continue

    for _ in range(needed):
        text, tag = random.choice(DEMO_NOTES)
        nd = date(2024, 9, 1) + timedelta(days=random.randint(0, 160))
        teacher = stu.get('teacher_name') or 'Teacher'
        # Avoid exact duplicate text for same student
        note_rows.append((sid, text, tag, nd, teacher))

if note_rows:
    execute_values(cur,
        """INSERT INTO teacher_notes (student_id, note_text, tag, note_date, created_by)
           VALUES %s""",
        note_rows)
    conn.commit()
print(f"4. Created {len(note_rows)} teacher notes")

conn.close()
print("\nDone! Student detail sample data generated.")
