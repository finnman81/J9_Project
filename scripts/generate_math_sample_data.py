"""
Generate sample math assessment data for all students in the database.
Creates Acadience Math assessments and calculates math scores.
Run once: python scripts/generate_math_sample_data.py
"""
import random
import sys
import numpy as np
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_connection, add_assessment, save_math_score
from core.math_calculations import (
    process_math_assessment_score,
    calculate_math_component_scores,
    calculate_overall_math_score,
    determine_math_risk_level,
    calculate_math_trend
)
from core.math_benchmarks import get_math_benchmark_thresholds, MATH_MEASURES_BY_GRADE, GRADE_ALIASES, PERIOD_MAP
from psycopg2.extras import execute_values
import pandas as pd

random.seed(77)
np.random.seed(77)

conn = get_db_connection()
cur = conn.cursor()

# ---------------------------------------------------------------------------
# Read existing students
# ---------------------------------------------------------------------------
students = pd.read_sql_query(
    """SELECT student_id, student_name, grade_level, class_name, teacher_name, school_year 
       FROM students 
       ORDER BY student_name, grade_level, school_year""",
    conn
)

print(f"Found {len(students)} student records")

# ---------------------------------------------------------------------------
# Define realistic score ranges based on benchmark thresholds
# ---------------------------------------------------------------------------
def get_score_range(measure: str, grade: str, period: str, ability: float) -> tuple:
    """Generate realistic score range based on benchmark thresholds and student ability."""
    thresholds = get_math_benchmark_thresholds(measure, grade, period)
    
    # Default ranges for grades/measures without benchmark data
    # These ranges are used when ability is applied, so they represent the full possible range
    default_ranges = {
        'Kindergarten': {
            # Wider ranges to allow high-ability students to score well
            'Math_Computation': {'Fall': (3, 20), 'Winter': (5, 20), 'Spring': (8, 20)},
        },
        'Third': {
            'Math_Computation': {'Fall': (10, 18), 'Winter': (12, 20), 'Spring': (14, 20)},
            'Math_Concepts_Application': {'Fall': (20, 50), 'Winter': (25, 55), 'Spring': (30, 60)},
            'Math_Composite': {'Fall': (20, 50), 'Winter': (30, 60), 'Spring': (35, 65)},
        },
        'Fourth': {
            'Math_Computation': {'Fall': (12, 20), 'Winter': (14, 20), 'Spring': (15, 20)},
            'Math_Concepts_Application': {'Fall': (25, 55), 'Winter': (30, 60), 'Spring': (35, 60)},
            'Math_Composite': {'Fall': (25, 55), 'Winter': (35, 60), 'Spring': (40, 65)},
        },
    }
    
    if not thresholds:
        # Use default ranges for grades without benchmark data
        if grade in default_ranges and measure in default_ranges[grade]:
            period_ranges = default_ranges[grade][measure]
            if period in period_ranges:
                lo, hi = period_ranges[period]
                # Apply ability to get score in range
                # Higher ability = higher score
                # For high ability (>0.7), ensure scores are in upper portion of range
                if ability > 0.7:
                    # High ability: use 70-100% of range
                    effective_ability = 0.7 + (ability - 0.7) * 1.5  # Stretch upper range
                    effective_ability = min(effective_ability, 0.95)
                else:
                    effective_ability = ability
                score = lo + (hi - lo) * effective_ability
                return (max(1, int(score)), int(score))
        
        # Generic fallback ranges
        if measure == 'NIF':
            return (15, 50)
        elif measure == 'NNF':
            return (8, 20)
        elif measure == 'AQD':
            return (8, 25)
        elif measure == 'MNF':
            return (3, 12)
        elif measure == 'Math_Computation':
            return (5, 18)
        elif measure == 'Math_Concepts_Application':
            return (10, 50)
        elif measure == 'Math_Composite':
            if grade == '1':
                return (80, 200) if period != 'EOY' else (50, 200)
            elif grade == '2':
                return (20, 60)
            else:
                return (25, 60)
        return (10, 50)
    
    above = thresholds['above_benchmark']
    goal = thresholds['benchmark_goal']
    cut = thresholds['cut_point_risk']
    
    # Generate score based on ability (0.0-1.0)
    # With Beta(5,1) distribution: ~80% have ability > 0.7, ~15% have 0.4-0.7, ~5% have < 0.4
    # ability 0.0-0.25: Well Below (below cut) - ~5%
    # ability 0.25-0.50: Below (cut to goal) - ~10%
    # ability 0.50-0.75: At (goal to above) - ~20%
    # ability 0.75-1.0: Above (above threshold) - ~65%
    
    if ability < 0.25:
        # Well Below Benchmark (~5% of students)
        score = random.uniform(max(1, cut * 0.75), cut * 0.95)
    elif ability < 0.50:
        # Below Benchmark (~10% of students)
        score = random.uniform(cut * 0.95, goal * 0.98)
    elif ability < 0.75:
        # At Benchmark (~20% of students)
        score = random.uniform(goal * 0.98, above * 1.15)
    else:
        # Above Benchmark (~65% of students) - ensure scores normalize to 70+
        # For measures with max_value, ensure score is high enough
        if measure in ['Math_Computation', 'NIF', 'NNF', 'AQD', 'MNF', 'Math_Concepts_Application']:
            # These normalize by max_value, so ensure high raw scores
            score = random.uniform(above * 1.2, above * 2.0)
        else:
            # Math_Composite - use high multiplier
            score = random.uniform(above * 1.3, above * 2.0)
    
    return (max(1, int(score)), int(score))

# ---------------------------------------------------------------------------
# Generate math assessments for each student
# ---------------------------------------------------------------------------
assessment_rows = []
school_year = '2024-25'

for _, stu in students.iterrows():
    sid = int(stu['student_id'])
    grade = stu['grade_level']
    grade_alias = GRADE_ALIASES.get(grade, '')
    
    # Get measures for this grade
    measures = MATH_MEASURES_BY_GRADE.get(grade_alias, [])
    
    # Handle grades not in MATH_MEASURES_BY_GRADE
    if not measures:
        if grade == 'Kindergarten':
            # Kindergarten: Only computation (no composite needed for overall score calculation)
            measures = ['Math_Computation']
        elif grade in ['Third', 'Fourth']:
            # Third and Fourth: Same as Second grade
            measures = ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite']
        else:
            continue
    
    # Generate student ability (consistent across periods)
    # Very heavily skewed distribution: most students doing well
    # Beta(5, 1) creates: ~80% At/Above Benchmark, ~15% Below, ~5% Well Below
    ability_raw = np.random.beta(5, 1)  # Very strong right skew - most students perform well
    ability = max(0.25, min(0.98, ability_raw))
    
    # Determine which periods to generate based on grade
    if grade == 'First':
        periods = ['Fall', 'Winter', 'Spring']
    else:
        periods = ['Fall', 'Winter', 'Spring']
    
    for period in periods:
        period_alias = PERIOD_MAP.get(period, period)
        
        for measure in measures:
            # Skip if no benchmark data for this measure/period
            thresholds = get_math_benchmark_thresholds(measure, grade, period_alias)
            if not thresholds and measure != 'Math_Composite':
                # Some measures only available in certain periods
                if measure == 'NIF' and period != 'Fall':
                    continue
                if measure == 'NNF' and period != 'Fall':
                    continue
                if measure == 'AQD' and period not in ['Fall', 'Winter']:
                    continue
                if measure == 'MNF' and period not in ['Fall', 'Winter']:
                    continue
            
            # Generate score
            score_val, score_raw = get_score_range(measure, grade, period_alias, ability)
            
            # Ensure score is never 0
            score_val = max(1, score_val)
            
            # Add some variation (but keep it positive)
            # For high-ability students, don't reduce scores too much
            if ability > 0.7:
                variation_factor = 0.05  # Less variation for high performers
            else:
                variation_factor = 0.08
            score_val = max(1, int(score_val + np.random.normal(0, max(1, score_val * variation_factor))))
            
            # For high-ability students, ensure minimum score to guarantee 70+ normalized
            if ability > 0.75:
                # Ensure raw score is high enough to normalize to 70+
                if measure == 'Math_Computation':
                    score_val = max(score_val, 14)  # 14/20 = 70%
                elif measure in ['NIF', 'NNF', 'AQD', 'MNF']:
                    # These have max values, ensure high enough raw score
                    math_types = {'NIF': 60, 'NNF': 70, 'AQD': 30, 'MNF': 15}
                    max_val = math_types.get(measure, 20)
                    min_raw = int(max_val * 0.7)  # 70% of max
                    score_val = max(score_val, min_raw)
                elif measure == 'Math_Concepts_Application':
                    score_val = max(score_val, 42)  # 42/60 = 70%
            
            # Normalize score AFTER adding variation
            score_normalized = process_math_assessment_score(
                measure, str(score_val), grade, period
            )
            
            # Fallback if normalization failed
            if score_normalized is None or score_normalized == 0:
                # Use a simple percentage if normalization fails
                if measure == 'Math_Composite':
                    # For composite, use grade-specific max
                    grade_maxes = {'Kindergarten': 200, 'First': 400, 'Second': 150, 'Third': 150, 'Fourth': 150}
                    max_val = grade_maxes.get(grade, 200)
                    score_normalized = min((score_val / max_val) * 100, 100)
                else:
                    score_normalized = min(score_val * 5, 100)  # Rough estimate
            
            assessment_rows.append((
                sid, measure, period, school_year,
                str(score_val), score_normalized,
                None, None, None, 'System', 0, 0, 'Math'
            ))

if assessment_rows:
    execute_values(cur,
        """INSERT INTO assessments 
           (student_id, assessment_type, assessment_period, school_year,
            score_value, score_normalized, assessment_date, notes, concerns,
            entered_by, needs_review, is_draft, subject_area)
           VALUES %s 
           ON CONFLICT (student_id, assessment_type, assessment_period, school_year)
           DO UPDATE SET
               score_value = EXCLUDED.score_value,
               score_normalized = EXCLUDED.score_normalized,
               subject_area = EXCLUDED.subject_area""",
        assessment_rows)
    conn.commit()
    print(f"1. Created {len(assessment_rows)} math assessment records")

# ---------------------------------------------------------------------------
# Calculate and save math scores for each student/period
# ---------------------------------------------------------------------------
from core.database import get_student_assessments

math_score_rows = []
students_processed = students['student_id'].unique()

for student_id in students_processed:
    # Get student info
    student_info = students[students['student_id'] == student_id].iloc[0]
    grade_level = student_info['grade_level']
    
    # Get all math assessments for this student
    assessments = get_student_assessments(student_id, school_year)
    math_assessments = assessments[assessments['subject_area'] == 'Math']
    
    if math_assessments.empty:
        continue
    
    # Process each assessment period
    for period in ['Fall', 'Winter', 'Spring', 'EOY']:
        period_assessments = math_assessments[math_assessments['assessment_period'] == period]
        
        if period_assessments.empty:
            continue
        
        # Calculate components
        components = calculate_math_component_scores(period_assessments, period, grade_level)
        overall_score, component_scores = calculate_overall_math_score(components, grade_level)
        
        if overall_score is None:
            continue
        
        # Determine risk level
        risk_level = determine_math_risk_level(overall_score)
        
        # Calculate trend
        trend = 'Unknown'
        if period != 'Fall':
            prev_period = 'Fall' if period == 'Winter' else ('Winter' if period == 'Spring' else 'Spring')
            prev_assessments = math_assessments[math_assessments['assessment_period'] == prev_period]
            if not prev_assessments.empty:
                prev_components = calculate_math_component_scores(prev_assessments, prev_period, grade_level)
                prev_overall, _ = calculate_overall_math_score(prev_components, grade_level)
                if prev_overall is not None:
                    trend = calculate_math_trend(overall_score, prev_overall)
        
        math_score_rows.append((
            student_id, school_year, period,
            round(overall_score, 2),
            round(component_scores.get('computation'), 2) if component_scores.get('computation') else None,
            round(component_scores.get('concepts'), 2) if component_scores.get('concepts') else None,
            round(component_scores.get('number_fluency'), 2) if component_scores.get('number_fluency') else None,
            round(component_scores.get('quantity_discrimination'), 2) if component_scores.get('quantity_discrimination') else None,
            risk_level, trend
        ))

if math_score_rows:
    execute_values(cur,
        """INSERT INTO math_scores 
           (student_id, school_year, assessment_period, overall_math_score,
            computation_component, concepts_component, number_fluency_component,
            quantity_discrimination_component, risk_level, trend)
           VALUES %s
           ON CONFLICT (student_id, school_year, assessment_period)
           DO UPDATE SET
               overall_math_score = EXCLUDED.overall_math_score,
               computation_component = EXCLUDED.computation_component,
               concepts_component = EXCLUDED.concepts_component,
               number_fluency_component = EXCLUDED.number_fluency_component,
               quantity_discrimination_component = EXCLUDED.quantity_discrimination_component,
               risk_level = EXCLUDED.risk_level,
               trend = EXCLUDED.trend,
               calculated_at = NOW()""",
        math_score_rows)
    conn.commit()
    print(f"2. Created/updated {len(math_score_rows)} math score records")

# ---------------------------------------------------------------------------
# Generate ERB Math scores for grades K-4
# ---------------------------------------------------------------------------
erb_math_rows = []
erb_students = students[students['grade_level'].isin(['Kindergarten', 'First', 'Second', 'Third', 'Fourth'])]

STANINE_PCT_MID = {1: 4, 2: 11, 3: 23, 4: 40, 5: 50, 6: 60, 7: 77, 8: 89, 9: 96}

for _, stu in erb_students.iterrows():
    sid = int(stu['student_id'])
    
    # Base ability from math scores if available
    math_scores_df = pd.read_sql_query(
        """SELECT overall_math_score FROM math_scores 
           WHERE student_id = %s AND school_year = %s
           ORDER BY calculated_at DESC LIMIT 1""",
        conn, params=[sid, school_year]
    )
    
    if not math_scores_df.empty:
        math_score = math_scores_df.iloc[0]['overall_math_score']
        # Convert 0-100 score to stanine-like ability (1-9)
        ability = max(1, min(9, (math_score / 100) * 9))
    else:
        ability = max(1, min(9, np.random.normal(5.5, 2.0)))
    
    # Generate ERB Math score
    stanine = int(np.clip(round(ability + np.random.normal(0, 0.9)), 1, 9))
    pct_mid = STANINE_PCT_MID[stanine]
    percentile = int(np.clip(pct_mid + np.random.randint(-6, 7), 1, 99))
    scale_score = int(400 + stanine * 30 + np.random.randint(-15, 16))
    growth_pct = int(np.clip(np.random.normal(50, 18), 1, 99))
    
    # Format score value (canonical format)
    score_value = f"stanine:{stanine}|percentile:{percentile}|scale:{scale_score}|growth:{growth_pct}"
    
    erb_math_rows.append((
        sid, 'ERB_Mathematics', 'Spring', school_year,
        score_value, float(percentile),
        None, None, None, 'System', 0, 0, 'Math'
    ))

if erb_math_rows:
    execute_values(cur,
        """INSERT INTO assessments 
           (student_id, assessment_type, assessment_period, school_year,
            score_value, score_normalized, assessment_date, notes, concerns,
            entered_by, needs_review, is_draft, subject_area)
           VALUES %s
           ON CONFLICT (student_id, assessment_type, assessment_period, school_year)
           DO UPDATE SET
               score_value = EXCLUDED.score_value,
               score_normalized = EXCLUDED.score_normalized,
               subject_area = EXCLUDED.subject_area""",
        erb_math_rows)
    conn.commit()
    print(f"3. Created {len(erb_math_rows)} ERB Mathematics assessment records")

conn.close()
print("\nDone! Math sample data generated successfully.")
print(f"\nSummary:")
print(f"  - Math assessments: {len(assessment_rows)}")
print(f"  - Math scores calculated: {len(math_score_rows)}")
print(f"  - ERB Math scores: {len(erb_math_rows)}")
