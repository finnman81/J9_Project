"""
Migrate math assessment data from CSV files to database.
Handles 1st Grade (complex) and 2nd-4th Grade (simpler) formats.
"""
import pandas as pd
import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import (
    get_db_connection, create_student, add_assessment, get_student_id
)
from core.math_calculations import process_math_assessment_score
from core.utils import recalculate_math_scores

def parse_first_grade_csv(file_path: str, school_year: str = '2025-26'):
    """Parse 1st grade math CSV format."""
    # Read CSV, skipping header rows
    df = pd.read_csv(file_path, skiprows=3)
    
    # Column mapping for 1st grade
    # Expected columns: Name, Class, NIF Fall, NNF Fall, AQD Fall, MNF Fall, 
    # Computation Fall, Composite Fall, AQD MOY, MNF MOY, Computation MOY, 
    # Composite MOY, [EOY columns...]
    
    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]
    
    students_created = 0
    assessments_added = 0
    
    for idx, row in df.iterrows():
        student_name = str(row.iloc[0]).strip()
        if pd.isna(student_name) or student_name == '' or student_name == 'nan':
            continue
        
        class_name = str(row.iloc[1]).strip() if len(row) > 1 else None
        if class_name == 'nan':
            class_name = None
        
        # Determine grade level from file name or default to First
        grade_level = 'First'
        
        # Create/update student
        student_id = get_student_id(student_name, grade_level, school_year)
        if not student_id:
            student_id = create_student(
                student_name=student_name,
                grade_level=grade_level,
                class_name=class_name,
                school_year=school_year
            )
            students_created += 1
        else:
            # Update class if needed
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE students SET class_name = %s WHERE student_id = %s
            ''', (class_name, student_id))
            conn.commit()
            conn.close()
        
        # Parse Fall assessments (columns 2-7: NIF, NNF, AQD, MNF, Computation, Composite)
        if len(row) > 7:
            measures_fall = ['NIF', 'NNF', 'AQD', 'MNF', 'Math_Computation', 'Math_Composite']
            for i, measure in enumerate(measures_fall, start=2):
                if i < len(row):
                    score_val = row.iloc[i]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'Fall'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='Fall',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} Fall for {student_name}: {e}")
        
        # Parse MOY assessments (columns 8-11: AQD, MNF, Computation, Composite)
        if len(row) > 11:
            measures_moy = ['AQD', 'MNF', 'Math_Computation', 'Math_Composite']
            moy_start_col = 8
            for i, measure in enumerate(measures_moy):
                col_idx = moy_start_col + i
                if col_idx < len(row):
                    score_val = row.iloc[col_idx]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'Winter'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='Winter',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} MOY for {student_name}: {e}")
        
        # Parse EOY assessments (columns 12-15: AQD, MNF, Computation, Composite)
        if len(row) > 15:
            measures_eoy = ['AQD', 'MNF', 'Math_Computation', 'Math_Composite']
            eoy_start_col = 12
            for i, measure in enumerate(measures_eoy):
                col_idx = eoy_start_col + i
                if col_idx < len(row):
                    score_val = row.iloc[col_idx]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'EOY'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='EOY',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} EOY for {student_name}: {e}")
    
    return students_created, assessments_added

def parse_second_grade_csv(file_path: str, school_year: str = '2025-26'):
    """Parse 2nd grade math CSV format (simpler: Computation, Concepts & Application, Composite)."""
    # Read CSV, skipping header rows
    df = pd.read_csv(file_path, skiprows=3)
    
    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]
    
    students_created = 0
    assessments_added = 0
    
    for idx, row in df.iterrows():
        student_name = str(row.iloc[0]).strip()
        if pd.isna(student_name) or student_name == '' or student_name == 'nan':
            continue
        
        class_name = str(row.iloc[1]).strip() if len(row) > 1 else None
        if class_name == 'nan':
            class_name = None
        
        grade_level = 'Second'
        
        # Create/update student
        student_id = get_student_id(student_name, grade_level, school_year)
        if not student_id:
            student_id = create_student(
                student_name=student_name,
                grade_level=grade_level,
                class_name=class_name,
                school_year=school_year
            )
            students_created += 1
        else:
            # Update class if needed
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE students SET class_name = %s WHERE student_id = %s
            ''', (class_name, student_id))
            conn.commit()
            conn.close()
        
        # Parse Fall assessments (columns 2-4: Computation, Concepts & Application, Composite)
        if len(row) > 4:
            measures_fall = ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite']
            for i, measure in enumerate(measures_fall, start=2):
                if i < len(row):
                    score_val = row.iloc[i]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'Fall'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='Fall',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} Fall for {student_name}: {e}")
        
        # Parse MOY assessments (columns 5-7: Computation, Concepts & Application, Composite)
        if len(row) > 7:
            measures_moy = ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite']
            moy_start_col = 5
            for i, measure in enumerate(measures_moy):
                col_idx = moy_start_col + i
                if col_idx < len(row):
                    score_val = row.iloc[col_idx]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'Winter'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='Winter',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} MOY for {student_name}: {e}")
        
        # Parse EOY assessments (columns 8-10: Computation, Concepts & Application, Composite)
        if len(row) > 10:
            measures_eoy = ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite']
            eoy_start_col = 8
            for i, measure in enumerate(measures_eoy):
                col_idx = eoy_start_col + i
                if col_idx < len(row):
                    score_val = row.iloc[col_idx]
                    if pd.notna(score_val) and str(score_val).strip() != '':
                        try:
                            score_normalized = process_math_assessment_score(
                                measure, str(score_val), grade_level, 'EOY'
                            )
                            add_assessment(
                                student_id=student_id,
                                assessment_type=measure,
                                assessment_period='EOY',
                                school_year=school_year,
                                score_value=str(score_val),
                                score_normalized=score_normalized,
                                subject_area='Math'
                            )
                            assessments_added += 1
                        except Exception as e:
                            print(f"Error adding {measure} EOY for {student_name}: {e}")
    
    return students_created, assessments_added

def migrate_math_csv(file_path: str, grade_level: str = None, school_year: str = '2025-26'):
    """Migrate math CSV file to database.
    
    Args:
        file_path: Path to CSV file
        grade_level: Grade level ('First', 'Second', etc.) - auto-detected from filename if None
        school_year: School year string (default: '2025-26')
    """
    # Auto-detect grade from filename
    if grade_level is None:
        if '1st' in file_path or '1 ' in file_path:
            grade_level = 'First'
        elif '2nd' in file_path or '2 ' in file_path or 'Second' in file_path:
            grade_level = 'Second'
        else:
            grade_level = 'First'  # Default
    
    print(f"Migrating {file_path} for {grade_level} grade...")
    
    if grade_level == 'First':
        students, assessments = parse_first_grade_csv(file_path, school_year)
    else:
        students, assessments = parse_second_grade_csv(file_path, school_year)
    
    print(f"Created/updated {students} students")
    print(f"Added {assessments} assessments")
    
    # Recalculate math scores
    print("Recalculating math scores...")
    recalculated = recalculate_math_scores()
    print(f"Recalculated scores for {recalculated} students")
    
    return students, assessments

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python migrate_math_data.py <csv_file> [grade_level] [school_year]")
        print("Example: python migrate_math_data.py 'math_build/1st Grade 25_26 Math Benchmark - 1 25_26.csv' First 2025-26")
        sys.exit(1)
    
    file_path = sys.argv[1]
    grade_level = sys.argv[2] if len(sys.argv) > 2 else None
    school_year = sys.argv[3] if len(sys.argv) > 3 else '2025-26'
    
    migrate_math_csv(file_path, grade_level, school_year)
    print("Migration complete!")
