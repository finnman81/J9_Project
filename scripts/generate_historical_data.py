"""
Generate 2022-23 and 2023-24 historical data so trend charts show real trends.
Run once:  python generate_historical_data.py
"""
import random
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_connection
from psycopg2.extras import execute_values
import pandas as pd

random.seed(99)
np.random.seed(99)

conn = get_db_connection()
cur = conn.cursor()

# ---------------------------------------------------------------------------
# Grade progression (go backwards from current grade)
# ---------------------------------------------------------------------------
PREV_GRADE = {
    'Fourth':       ['Third', 'Second'],
    'Third':        ['Second', 'First'],
    'Second':       ['First', 'Kindergarten'],
    'First':        ['Kindergarten', None],
    'Kindergarten': [None, None],
}
HISTORICAL_YEARS = ['2023-24', '2022-23']

# Read current students (2024-25)
current = pd.read_sql_query(
    "SELECT DISTINCT student_name, grade_level, class_name, teacher_name "
    "FROM students WHERE school_year = '2024-25'", conn)
print(f"Found {len(current)} current-year student records")

# ---------------------------------------------------------------------------
# 1. Create historical student records
# ---------------------------------------------------------------------------
student_rows = []
for _, row in current.iterrows():
    prev_grades = PREV_GRADE.get(row['grade_level'], [None, None])
    for i, year in enumerate(HISTORICAL_YEARS):
        prev_g = prev_grades[i] if i < len(prev_grades) else None
        if prev_g is None:
            continue  # student didn't exist yet
        student_rows.append((
            row['student_name'], prev_g, row['class_name'],
            row['teacher_name'], year))

if student_rows:
    execute_values(cur,
        """INSERT INTO students (student_name, grade_level, class_name, teacher_name, school_year)
           VALUES %s
           ON CONFLICT (student_name, grade_level, school_year) DO NOTHING""",
        student_rows)
    conn.commit()
print(f"1. Inserted up to {len(student_rows)} historical student records")

# ---------------------------------------------------------------------------
# 2. Create historical literacy scores with realistic progression
# ---------------------------------------------------------------------------
# Fetch all students with IDs (including new historical ones)
all_students = pd.read_sql_query(
    "SELECT student_id, student_name, grade_level, school_year FROM students "
    "ORDER BY student_name, school_year", conn)

# Get current-year scores to base historical scores on
current_scores = pd.read_sql_query("""
    SELECT s.student_name, ls.overall_literacy_score, ls.risk_level,
           ls.reading_component, ls.phonics_component, ls.sight_words_component
    FROM students s
    JOIN literacy_scores ls ON ls.student_id = s.student_id
    WHERE s.school_year = '2024-25'
      AND ls.score_id = (
          SELECT score_id FROM literacy_scores ls2
          WHERE ls2.student_id = s.student_id
          ORDER BY ls2.calculated_at DESC LIMIT 1)
""", conn)
score_lookup = dict(zip(current_scores['student_name'],
                        current_scores['overall_literacy_score']))

# For each historical student, generate scores across Fall/Winter/Spring
# Scores should be LOWER in earlier years (showing growth over time)
periods = ['Fall', 'Winter', 'Spring']
score_rows = []
historical = all_students[all_students['school_year'].isin(HISTORICAL_YEARS)]

for _, stu in historical.iterrows():
    sid = int(stu['student_id'])
    name = stu['student_name']
    year = stu['school_year']

    # Base: current score with some regression for older years
    current_score = score_lookup.get(name)
    if current_score is None or np.isnan(current_score):
        current_score = np.random.normal(65, 18)

    # Older year = lower scores (students grow ~5-12 pts per year)
    year_offset = 2 if year == '2022-23' else 1
    base = current_score - year_offset * np.random.uniform(5, 14)
    base = max(10, min(95, base))

    for j, period in enumerate(periods):
        # Within-year growth: Fall < Winter < Spring
        period_growth = j * np.random.uniform(2, 6)
        score = base + period_growth + np.random.normal(0, 3)
        score = max(5, min(100, round(score, 1)))

        # Component scores
        reading = max(0, min(100, score + np.random.normal(0, 5)))
        phonics = max(0, min(100, score + np.random.normal(-3, 6)))
        sight_w = max(0, min(100, score + np.random.normal(2, 5)))

        # Risk level
        if score >= 70:
            risk = 'Low'
        elif score >= 50:
            risk = 'Medium'
        else:
            risk = 'High'

        # Trend
        if j == 0:
            trend = 'New'
        elif period_growth > 3:
            trend = 'Improving'
        elif period_growth < 1:
            trend = 'Declining'
        else:
            trend = 'Stable'

        score_rows.append((
            sid, year, period, round(score, 1),
            round(reading, 1), round(phonics, 1), None, round(sight_w, 1),
            risk, trend))

if score_rows:
    execute_values(cur,
        """INSERT INTO literacy_scores
               (student_id, school_year, assessment_period, overall_literacy_score,
                reading_component, phonics_component, spelling_component,
                sight_words_component, risk_level, trend)
           VALUES %s
           ON CONFLICT (student_id, school_year, assessment_period) DO NOTHING""",
        score_rows)
    conn.commit()
print(f"2. Inserted up to {len(score_rows)} historical literacy score records")

# ---------------------------------------------------------------------------
# 3. Verify the trend data now spans multiple years
# ---------------------------------------------------------------------------
verify = pd.read_sql_query("""
    SELECT school_year, risk_level, COUNT(*) as n
    FROM (
        SELECT ls.student_id, ls.school_year, ls.risk_level,
               ROW_NUMBER() OVER (PARTITION BY ls.student_id, ls.school_year
                                  ORDER BY ls.calculated_at DESC) as rn
        FROM literacy_scores ls
    ) sub WHERE rn = 1
    GROUP BY school_year, risk_level
    ORDER BY school_year, risk_level
""", conn)
print("\n3. Risk level distribution by year:")
print(verify.to_string())

conn.close()
print("\nDone! Historical data generated.")
