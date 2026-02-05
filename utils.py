"""
Utility functions for recalculating literacy scores
"""
import pandas as pd
from database import get_db_connection, get_student_assessments, save_literacy_score
from calculations import (
    calculate_component_scores, calculate_overall_literacy_score,
    determine_risk_level, calculate_trend
)

def recalculate_literacy_scores(student_id: int = None, school_year: str = None):
    """Recalculate literacy scores for students"""
    conn = get_db_connection()
    
    # Get all students or specific student
    if student_id:
        query = 'SELECT DISTINCT student_id, school_year FROM students WHERE student_id = ?'
        params = [student_id]
    else:
        query = 'SELECT DISTINCT student_id, school_year FROM students'
        params = []
    
    if school_year:
        query += ' AND school_year = ?'
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

if __name__ == '__main__':
    import pandas as pd
    recalculate_literacy_scores()
