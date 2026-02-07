"""
Database connection and schema setup for Literacy Assessment System
"""
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

DB_PATH = 'database/literacy_assessments.db'


def _ensure_column(cursor, table_name: str, column_name: str, column_def: str):
    """Add a column if it does not yet exist."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

def get_db_connection():
    """Get SQLite database connection"""
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def init_database():
    """Initialize database schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            class_name TEXT,
            teacher_name TEXT,
            school_year TEXT NOT NULL DEFAULT '2024-25',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_name, grade_level, school_year)
        )
    ''')
    
    # Assessments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            assessment_type TEXT NOT NULL,
            assessment_period TEXT NOT NULL,
            school_year TEXT NOT NULL,
            score_value TEXT,
            score_normalized REAL,
            assessment_date DATE,
            notes TEXT,
            concerns TEXT,
            entered_by TEXT,
            needs_review INTEGER DEFAULT 0,
            is_draft INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, assessment_type, assessment_period, school_year)
        )
    ''')

    # Backwards-compatible schema updates for existing databases
    _ensure_column(cursor, 'assessments', 'needs_review', 'INTEGER DEFAULT 0')
    _ensure_column(cursor, 'assessments', 'is_draft', 'INTEGER DEFAULT 0')
    
    # Interventions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interventions (
            intervention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            intervention_type TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            frequency TEXT,
            duration_minutes INTEGER,
            status TEXT NOT NULL DEFAULT 'Active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')
    
    # Literacy scores table (calculated/denormalized)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS literacy_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            school_year TEXT NOT NULL,
            assessment_period TEXT NOT NULL,
            overall_literacy_score REAL,
            reading_component REAL,
            phonics_component REAL,
            spelling_component REAL,
            sight_words_component REAL,
            risk_level TEXT,
            trend TEXT,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, school_year, assessment_period)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            note_text TEXT NOT NULL,
            tag TEXT,
            note_date DATE,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_goals (
            goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            measure TEXT NOT NULL,
            baseline_score REAL,
            target_score REAL,
            expected_weekly_growth REAL,
            start_date DATE,
            target_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')
    
    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_teacher ON students(teacher_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(assessment_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_interventions_student ON interventions(student_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_literacy_scores_student ON literacy_scores(student_id)')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

def get_student_id(student_name: str, grade_level: str, school_year: str) -> Optional[int]:
    """Get student ID by name, grade, and year"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT student_id FROM students 
        WHERE student_name = ? AND grade_level = ? AND school_year = ?
    ''', (student_name, grade_level, school_year))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def create_student(student_name: str, grade_level: str, class_name: str = None, 
                   teacher_name: str = None, school_year: str = '2024-25') -> int:
    """Create a new student and return student_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO students 
        (student_name, grade_level, class_name, teacher_name, school_year)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_name, grade_level, class_name, teacher_name, school_year))
    conn.commit()
    student_id = cursor.lastrowid
    if student_id == 0:
        # Student already exists, get the ID
        student_id = get_student_id(student_name, grade_level, school_year)
    conn.close()
    return student_id

def add_assessment(student_id: int, assessment_type: str, assessment_period: str,
                   school_year: str, score_value: str = None, score_normalized: float = None,
                   assessment_date: str = None, notes: str = None, concerns: str = None,
                   entered_by: str = None, needs_review: bool = False, is_draft: bool = False):
    """Add an assessment record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO assessments
        (student_id, assessment_type, assessment_period, school_year, score_value,
         score_normalized, assessment_date, notes, concerns, entered_by, needs_review, is_draft)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, assessment_type, assessment_period, school_year, score_value,
          score_normalized, assessment_date, notes, concerns, entered_by, int(needs_review), int(is_draft)))
    conn.commit()
    conn.close()


def add_teacher_note(student_id: int, note_text: str, tag: str = None,
                     note_date: str = None, created_by: str = 'Teacher'):
    """Add a teacher note with optional tag/date."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO teacher_notes
        (student_id, note_text, tag, note_date, created_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, note_text, tag, note_date, created_by))
    conn.commit()
    conn.close()


def get_teacher_notes(student_id: int) -> pd.DataFrame:
    """Get teacher notes for a student."""
    conn = get_db_connection()
    df = pd.read_sql_query('''
        SELECT * FROM teacher_notes
        WHERE student_id = ?
        ORDER BY COALESCE(note_date, created_at) DESC
    ''', conn, params=[student_id])
    conn.close()
    return df


def upsert_student_goal(student_id: int, measure: str, baseline_score: float,
                        target_score: float, expected_weekly_growth: float,
                        start_date: str = None, target_date: str = None):
    """Create or update a goal for a student and measure.

    If a goal already exists for the same student_id + measure, it is updated.
    Otherwise a new row is inserted.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if goal already exists for this student + measure
    cursor.execute(
        'SELECT goal_id FROM student_goals WHERE student_id = ? AND measure = ?',
        (student_id, measure)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute('''
            UPDATE student_goals
            SET baseline_score = ?, target_score = ?, expected_weekly_growth = ?,
                start_date = ?, target_date = ?
            WHERE student_id = ? AND measure = ?
        ''', (baseline_score, target_score, expected_weekly_growth,
              start_date, target_date, student_id, measure))
    else:
        cursor.execute('''
            INSERT INTO student_goals
            (student_id, measure, baseline_score, target_score, expected_weekly_growth, start_date, target_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, measure, baseline_score, target_score, expected_weekly_growth, start_date, target_date))
    conn.commit()
    conn.close()


def get_student_goals(student_id: int) -> pd.DataFrame:
    """Get all goals for a student."""
    conn = get_db_connection()
    df = pd.read_sql_query('''
        SELECT * FROM student_goals
        WHERE student_id = ?
        ORDER BY created_at DESC
    ''', conn, params=[student_id])
    conn.close()
    return df

def add_intervention(student_id: int, intervention_type: str, start_date: str,
                     end_date: str = None, frequency: str = None, duration_minutes: int = None,
                     status: str = 'Active', notes: str = None):
    """Add an intervention record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interventions
        (student_id, intervention_type, start_date, end_date, frequency, duration_minutes, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, intervention_type, start_date, end_date, frequency, duration_minutes, status, notes))
    conn.commit()
    conn.close()

def save_literacy_score(student_id: int, school_year: str, assessment_period: str,
                        overall_score: float, reading_component: float = None,
                        phonics_component: float = None, spelling_component: float = None,
                        sight_words_component: float = None, risk_level: str = None,
                        trend: str = None):
    """Save calculated literacy score"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO literacy_scores
        (student_id, school_year, assessment_period, overall_literacy_score,
         reading_component, phonics_component, spelling_component, sight_words_component,
         risk_level, trend)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, school_year, assessment_period, overall_score,
          reading_component, phonics_component, spelling_component, sight_words_component,
          risk_level, trend))
    conn.commit()
    conn.close()

def get_all_students(grade_level: str = None, class_name: str = None, 
                     teacher_name: str = None, school_year: str = None) -> pd.DataFrame:
    """Get all students with optional filters"""
    conn = get_db_connection()
    query = 'SELECT * FROM students WHERE 1=1'
    params = []
    
    if grade_level:
        query += ' AND grade_level = ?'
        params.append(grade_level)
    if class_name:
        query += ' AND class_name = ?'
        params.append(class_name)
    if teacher_name:
        query += ' AND teacher_name = ?'
        params.append(teacher_name)
    if school_year:
        query += ' AND school_year = ?'
        params.append(school_year)
    
    query += ' ORDER BY student_name, grade_level'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_student_assessments(student_id: int, school_year: str = None) -> pd.DataFrame:
    """Get all assessments for a student"""
    conn = get_db_connection()
    query = '''
        SELECT a.*, s.student_name, s.grade_level 
        FROM assessments a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.student_id = ?
    '''
    params = [student_id]
    
    if school_year:
        query += ' AND a.school_year = ?'
        params.append(school_year)
    
    query += ' ORDER BY a.assessment_date DESC, a.assessment_period'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_student_interventions(student_id: int) -> pd.DataFrame:
    """Get all interventions for a student"""
    conn = get_db_connection()
    query = '''
        SELECT i.*, s.student_name 
        FROM interventions i
        JOIN students s ON i.student_id = s.student_id
        WHERE i.student_id = ?
        ORDER BY i.start_date DESC
    '''
    df = pd.read_sql_query(query, conn, params=[student_id])
    conn.close()
    return df

def get_latest_literacy_score(student_id: int, school_year: str = None) -> Optional[Dict]:
    """Get the latest literacy score for a student"""
    conn = get_db_connection()
    query = '''
        SELECT * FROM literacy_scores 
        WHERE student_id = ?
    '''
    params = [student_id]
    
    if school_year:
        query += ' AND school_year = ?'
        params.append(school_year)
    
    query += '''
        ORDER BY
            CASE assessment_period
                WHEN 'Fall' THEN 1
                WHEN 'Winter' THEN 2
                WHEN 'Spring' THEN 3
                WHEN 'EOY' THEN 4
                ELSE 0
            END DESC,
            calculated_at DESC
        LIMIT 1
    '''
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return dict(result)
    return None

if __name__ == '__main__':
    init_database()
