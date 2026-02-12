"""
Migration script to import normalized_grades.xlsx into SQLite database
"""
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import init_database, create_student, add_assessment, save_literacy_score, get_student_assessments
from core.calculations import process_assessment_score, calculate_component_scores, calculate_overall_literacy_score, determine_risk_level

def migrate_excel_to_database(excel_file: str = 'data/normalized_grades.xlsx', school_year: str = '2024-25'):
    """Migrate Excel data to SQLite database"""
    print("Initializing database...")
    init_database()
    
    print(f"Reading Excel file: {excel_file}")
    df = pd.read_excel(excel_file)
    
    print(f"Found {len(df)} records")
    
    # Grade level mapping
    grade_map = {
        'Kindergarten': 'Kindergarten',
        'First': 'First',
        'Second': 'Second',
        'Third': 'Third',
        'Fourth': 'Fourth'
    }
    
    # Assessment type mappings
    assessment_mappings = {
        'Reading_Level_Fall': ('Reading_Level', 'Fall'),
        'Reading_Level_Winter': ('Reading_Level', 'Winter'),
        'Reading_Level_Spring': ('Reading_Level', 'Spring'),
        'Reading_Level_EOY': ('Reading_Level', 'EOY'),
        'Reading_Level_1EOY': ('Reading_Level', 'EOY'),  # First grade EOY
        'Reading_Level_2EOY': ('Reading_Level', 'EOY'),  # Second grade EOY
        'Reading_Level_3EOY': ('Reading_Level', 'EOY'),  # Third grade EOY
        'Sight_Words_SeptNov': ('Sight_Words', 'Fall'),
        'Sight_Words_Winter': ('Sight_Words', 'Winter'),
        'Sight_Words_Spring': ('Sight_Words', 'Spring'),
        'Sight_Words_EOY': ('Sight_Words', 'EOY'),
        'Spelling_Fall': ('Spelling', 'Fall'),
        'Spelling_Spring': ('Spelling', 'Spring'),
        'Spelling_EOY': ('Spelling', 'EOY'),
        'Benchmark_Fall': ('Benchmark', 'Fall'),
        'Benchmark_Spring': ('Benchmark', 'Spring'),
        'Alphabet_Naming': ('Phonics_Survey', 'Fall'),
        'Slingerlands_Fall': ('Phonics_Survey', 'Fall'),
        'PAR_Fall': ('Benchmark', 'Fall'),
        'PAR_EOY': ('Benchmark', 'EOY'),
    }
    
    students_created = set()
    assessments_added = 0
    
    for idx, row in df.iterrows():
        student_name = str(row['Student_Name']).strip()
        grade_level = str(row['Grade_Level']).strip()
        
        # Create student (if not already created)
        student_key = (student_name, grade_level, school_year)
        if student_key not in students_created:
            student_id = create_student(
                student_name=student_name,
                grade_level=grade_level,
                class_name=None,  # Will be filled in later via data entry
                teacher_name=None,  # Will be filled in later via data entry
                school_year=school_year
            )
            students_created.add(student_key)
        else:
            # Get existing student ID
            from core.database import get_student_id
            student_id = get_student_id(student_name, grade_level, school_year)
        
        # Process each assessment column
        for col in df.columns:
            if col in ['Student_Name', 'Grade_Level', 'Concerns']:
                continue
            
            # Skip original columns (we'll use normalized ones)
            if col.endswith('_Original'):
                continue
            
            # Check if this column maps to an assessment
            if col in assessment_mappings:
                assessment_type, period = assessment_mappings[col]
                score_value = row[col]
                
                # Only add if score exists
                if pd.notna(score_value) and str(score_value).strip() != '':
                    # Normalize score
                    score_normalized = process_assessment_score(assessment_type, str(score_value))
                    
                    # Add assessment
                    add_assessment(
                        student_id=student_id,
                        assessment_type=assessment_type,
                        assessment_period=period,
                        school_year=school_year,
                        score_value=str(score_value),
                        score_normalized=score_normalized,
                        assessment_date=None,  # No exact dates in original data
                        notes=None,
                        concerns=str(row.get('Concerns', '')) if pd.notna(row.get('Concerns')) else None,
                        entered_by='Migration'
                    )
                    assessments_added += 1
        
        # Calculate and save literacy score for each period
        from core.database import get_student_assessments
        student_assessments = get_student_assessments(student_id, school_year)
        
        for period in ['Fall', 'Winter', 'Spring', 'EOY']:
            period_assessments = student_assessments[student_assessments['assessment_period'] == period]
            if not period_assessments.empty:
                components = calculate_component_scores(period_assessments, period)
                overall_score, component_scores = calculate_overall_literacy_score(components)
                
                if overall_score is not None:
                    risk_level = determine_risk_level(overall_score)
                    
                    # Calculate trend (compare to previous period)
                    trend = 'Unknown'
                    if period != 'Fall':
                        prev_period = 'Fall' if period == 'Winter' else ('Winter' if period == 'Spring' else 'Spring')
                        prev_assessments = student_assessments[student_assessments['assessment_period'] == prev_period]
                        if not prev_assessments.empty:
                            prev_components = calculate_component_scores(prev_assessments, prev_period)
                            prev_overall, _ = calculate_overall_literacy_score(prev_components)
                            if prev_overall is not None:
                                from core.calculations import calculate_trend
                                trend = calculate_trend(overall_score, prev_overall)
                    
                    save_literacy_score(
                        student_id=student_id,
                        school_year=school_year,
                        assessment_period=period,
                        overall_score=overall_score,
                        reading_component=component_scores.get('reading'),
                        phonics_component=component_scores.get('phonics_spelling'),
                        spelling_component=component_scores.get('phonics_spelling'),  # Combined
                        sight_words_component=component_scores.get('sight_words'),
                        risk_level=risk_level,
                        trend=trend
                    )
    
    print(f"\nMigration complete!")
    print(f"Students created: {len(students_created)}")
    print(f"Assessments added: {assessments_added}")

if __name__ == '__main__':
    migrate_excel_to_database()
