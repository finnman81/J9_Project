"""
Utility functions for recalculating literacy and math scores
"""
import pandas as pd
from core.database import get_db_connection, get_student_assessments, save_literacy_score, save_math_score
from core.calculations import (
    calculate_component_scores, calculate_overall_literacy_score,
    determine_risk_level, calculate_trend
)
from core.math_calculations import (
    calculate_math_component_scores, calculate_overall_math_score,
    determine_math_risk_level, calculate_math_trend
)

def recalculate_literacy_scores(student_id: int = None, school_year: str = None):
    """Recalculate literacy scores for students"""
    conn = get_db_connection()
    
    # Get all students or specific student
    if student_id:
        query = 'SELECT DISTINCT student_id, school_year FROM students WHERE student_id = %s'
        params = [student_id]
    else:
        query = 'SELECT DISTINCT student_id, school_year FROM students'
        params = []
    
    if school_year:
        query += ' AND school_year = %s'
        params.append(school_year)
    
    students_df = pd.read_sql_query(query, conn)
    conn.close()
    
    updated_count = 0
    
    for _, row in students_df.iterrows():
        sid = row['student_id']
        syear = row['school_year']
        
        # Get all assessments for this student
        assessments = get_student_assessments(sid, syear)
        
        if assessments.empty:
            continue
        
        # Process each assessment period
        for period in ['Fall', 'Winter', 'Spring', 'EOY']:
            period_assessments = assessments[assessments['assessment_period'] == period]
            
            if period_assessments.empty:
                continue
            
            # Calculate components
            components = calculate_component_scores(period_assessments, period)
            overall_score, component_scores = calculate_overall_literacy_score(components)
            
            if overall_score is not None:
                risk_level = determine_risk_level(overall_score)
                
                # Calculate trend
                trend = 'Unknown'
                if period != 'Fall':
                    prev_period = 'Fall' if period == 'Winter' else ('Winter' if period == 'Spring' else 'Spring')
                    prev_assessments = assessments[assessments['assessment_period'] == prev_period]
                    if not prev_assessments.empty:
                        prev_components = calculate_component_scores(prev_assessments, prev_period)
                        prev_overall, _ = calculate_overall_literacy_score(prev_components)
                        if prev_overall is not None:
                            trend = calculate_trend(overall_score, prev_overall)
                
                # Save literacy score
                save_literacy_score(
                    student_id=sid,
                    school_year=syear,
                    assessment_period=period,
                    overall_score=overall_score,
                    reading_component=component_scores.get('reading'),
                    phonics_component=component_scores.get('phonics_spelling'),
                    spelling_component=component_scores.get('phonics_spelling'),
                    sight_words_component=component_scores.get('sight_words'),
                    risk_level=risk_level,
                    trend=trend
                )
                updated_count += 1
    
    return updated_count

def recalculate_math_scores(student_id: int = None, school_year: str = None):
    """Recalculate math scores for students"""
    conn = get_db_connection()
    
    # Get all students or specific student
    if student_id:
        query = 'SELECT DISTINCT student_id, school_year FROM students WHERE student_id = %s'
        params = [student_id]
    else:
        query = 'SELECT DISTINCT student_id, school_year FROM students'
        params = []
    
    if school_year:
        query += ' AND school_year = %s'
        params.append(school_year)
    
    students_df = pd.read_sql_query(query, conn)
    conn.close()
    
    updated_count = 0
    
    for _, row in students_df.iterrows():
        sid = row['student_id']
        syear = row['school_year']
        
        # Get all math assessments for this student
        assessments = get_student_assessments(sid, syear)
        # Filter for math assessments
        if 'subject_area' in assessments.columns:
            math_assessments = assessments[assessments['subject_area'] == 'Math']
        else:
            # Fallback: filter by assessment type if subject_area column doesn't exist
            math_types = ['NIF', 'NNF', 'AQD', 'MNF', 'Math_Computation', 'Math_Concepts_Application', 
                         'Computation', 'Concepts_Application', 'Concepts & Application', 'Math_Composite']
            math_assessments = assessments[assessments['assessment_type'].isin(math_types)]
        
        if math_assessments.empty:
            continue
        
        # Get grade level for normalization
        conn = get_db_connection()
        grade_query = 'SELECT grade_level FROM students WHERE student_id = %s AND school_year = %s LIMIT 1'
        grade_df = pd.read_sql_query(grade_query, conn, params=[sid, syear])
        conn.close()
        grade_level = grade_df['grade_level'].iloc[0] if not grade_df.empty else None
        
        # Process each assessment period
        for period in ['Fall', 'Winter', 'Spring', 'EOY']:
            period_assessments = math_assessments[math_assessments['assessment_period'] == period]
            
            if period_assessments.empty:
                continue
            
            # Calculate components
            components = calculate_math_component_scores(period_assessments, period, grade_level)
            overall_score, component_scores = calculate_overall_math_score(components, grade_level)
            
            if overall_score is not None:
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
                
                # Save math score
                save_math_score(
                    student_id=sid,
                    school_year=syear,
                    assessment_period=period,
                    overall_score=overall_score,
                    computation_component=component_scores.get('computation'),
                    concepts_component=component_scores.get('concepts'),
                    number_fluency_component=component_scores.get('number_fluency'),
                    quantity_discrimination_component=component_scores.get('quantity_discrimination'),
                    risk_level=risk_level,
                    trend=trend
                )
                updated_count += 1
    
    return updated_count

if __name__ == '__main__':
    import pandas as pd
    recalculate_literacy_scores()
    recalculate_math_scores()