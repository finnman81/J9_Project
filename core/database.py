"""
Database connection and schema setup for Literacy Assessment System
Uses PostgreSQL via Supabase (connected with psycopg2)
"""
import warnings
warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')

import psycopg2
import psycopg2.extras
from psycopg2.extensions import register_adapter, AsIs
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
import streamlit as st

# ---------------------------------------------------------------------------
# Register numpy types so psycopg2 can handle them as query parameters
# ---------------------------------------------------------------------------

def _adapt_numpy_int(val):
    return AsIs(int(val))

def _adapt_numpy_float(val):
    return AsIs(float(val))

for _np_int_type in [np.int64, np.int32, np.int16, np.int8, np.intp]:
    register_adapter(_np_int_type, _adapt_numpy_int)
for _np_float_type in [np.float64, np.float32, np.float16]:
    register_adapter(_np_float_type, _adapt_numpy_float)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db_connection():
    """Get PostgreSQL database connection to Supabase.
    
    Reads the connection string from Streamlit secrets (preferred)
    or the DATABASE_URL environment variable as fallback.
    """
    db_url = None
    # Try Streamlit secrets first
    try:
        db_url = st.secrets["DATABASE_URL"]
    except Exception:
        pass
    # Fallback to env var
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL not found. Set it in .streamlit/secrets.toml "
            "or as an environment variable."
        )
    conn = psycopg2.connect(db_url)
    return conn


def _dict_cursor(conn):
    """Return a cursor that yields dicts instead of tuples."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ---------------------------------------------------------------------------
# Schema initialisation (run once via Supabase SQL Editor or this helper)
# ---------------------------------------------------------------------------

def init_database():
    """Initialize database schema.
    
    Safe to call repeatedly -- uses IF NOT EXISTS.  For Supabase the
    preferred path is running schema/supabase_schema.sql in the SQL Editor, but
    this function works as a fallback for local Postgres too.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id SERIAL PRIMARY KEY,
            student_name TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            class_name TEXT,
            teacher_name TEXT,
            school_year TEXT NOT NULL DEFAULT '2024-25',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(student_name, grade_level, school_year)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            assessment_type TEXT NOT NULL,
            assessment_period TEXT NOT NULL,
            school_year TEXT NOT NULL,
            score_value TEXT,
            score_normalized DOUBLE PRECISION,
            assessment_date DATE,
            notes TEXT,
            concerns TEXT,
            entered_by TEXT,
            needs_review INTEGER DEFAULT 0,
            is_draft INTEGER DEFAULT 0,
            subject_area TEXT DEFAULT 'Reading',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(student_id, assessment_type, assessment_period, school_year)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interventions (
            intervention_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            intervention_type TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            frequency TEXT,
            duration_minutes INTEGER,
            status TEXT NOT NULL DEFAULT 'Active',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS literacy_scores (
            score_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            school_year TEXT NOT NULL,
            assessment_period TEXT NOT NULL,
            overall_literacy_score DOUBLE PRECISION,
            reading_component DOUBLE PRECISION,
            phonics_component DOUBLE PRECISION,
            spelling_component DOUBLE PRECISION,
            sight_words_component DOUBLE PRECISION,
            risk_level TEXT,
            trend TEXT,
            calculated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(student_id, school_year, assessment_period)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_notes (
            note_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            note_text TEXT NOT NULL,
            tag TEXT,
            note_date DATE,
            created_by TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_goals (
            goal_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            measure TEXT NOT NULL,
            baseline_score DOUBLE PRECISION,
            target_score DOUBLE PRECISION,
            expected_weekly_growth DOUBLE PRECISION,
            start_date DATE,
            target_date DATE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS math_scores (
            score_id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(student_id),
            school_year TEXT NOT NULL,
            assessment_period TEXT NOT NULL,
            overall_math_score DOUBLE PRECISION,
            computation_component DOUBLE PRECISION,
            concepts_component DOUBLE PRECISION,
            number_fluency_component DOUBLE PRECISION,
            quantity_discrimination_component DOUBLE PRECISION,
            risk_level TEXT,
            trend TEXT,
            calculated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(student_id, school_year, assessment_period)
        )
    ''')

    # Indexes
    for idx_sql in [
        'CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade_level)',
        'CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name)',
        'CREATE INDEX IF NOT EXISTS idx_students_teacher ON students(teacher_name)',
        'CREATE INDEX IF NOT EXISTS idx_students_year ON students(school_year)',
        'CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id)',
        'CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(assessment_type)',
        'CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(subject_area)',
        'CREATE INDEX IF NOT EXISTS idx_interventions_student ON interventions(student_id)',
        'CREATE INDEX IF NOT EXISTS idx_literacy_scores_student ON literacy_scores(student_id)',
        'CREATE INDEX IF NOT EXISTS idx_math_scores_student ON math_scores(student_id)',
        'CREATE INDEX IF NOT EXISTS idx_math_scores_year ON math_scores(school_year)',
        'CREATE INDEX IF NOT EXISTS idx_math_scores_period ON math_scores(assessment_period)',
        'CREATE INDEX IF NOT EXISTS idx_teacher_notes_student ON teacher_notes(student_id)',
        'CREATE INDEX IF NOT EXISTS idx_student_goals_student ON student_goals(student_id)',
    ]:
        cursor.execute(idx_sql)

    conn.commit()
    conn.close()
    print("Database initialized successfully")

# ---------------------------------------------------------------------------
# Student helpers
# ---------------------------------------------------------------------------

def get_student_id(student_name: str, grade_level: str, school_year: str) -> Optional[int]:
    """Get student ID by name, grade, and year."""
    conn = get_db_connection()
    cur = _dict_cursor(conn)
    cur.execute(
        'SELECT student_id FROM students WHERE student_name = %s AND grade_level = %s AND school_year = %s',
        (student_name, grade_level, school_year),
    )
    result = cur.fetchone()
    conn.close()
    return result['student_id'] if result else None


def create_student(student_name: str, grade_level: str, class_name: str = None,
                   teacher_name: str = None, school_year: str = '2024-25') -> int:
    """Create a new student and return student_id.  If already exists, return existing id."""
    conn = get_db_connection()
    cur = _dict_cursor(conn)
    cur.execute('''
        INSERT INTO students (student_name, grade_level, class_name, teacher_name, school_year)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (student_name, grade_level, school_year) DO NOTHING
        RETURNING student_id
    ''', (student_name, grade_level, class_name, teacher_name, school_year))
    row = cur.fetchone()
    conn.commit()
    if row:
        student_id = row['student_id']
    else:
        student_id = get_student_id(student_name, grade_level, school_year)
    conn.close()
    return student_id

# ---------------------------------------------------------------------------
# Assessment helpers
# ---------------------------------------------------------------------------

def add_assessment(student_id: int, assessment_type: str, assessment_period: str,
                   school_year: str, score_value: str = None, score_normalized: float = None,
                   assessment_date: str = None, notes: str = None, concerns: str = None,
                   entered_by: str = None, needs_review: bool = False, is_draft: bool = False,
                   subject_area: str = 'Reading'):
    """Add an assessment record (upsert on unique constraint)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO assessments
            (student_id, assessment_type, assessment_period, school_year, score_value,
             score_normalized, assessment_date, notes, concerns, entered_by, needs_review, is_draft, subject_area)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, assessment_type, assessment_period, school_year)
        DO UPDATE SET
            score_value = EXCLUDED.score_value,
            score_normalized = EXCLUDED.score_normalized,
            assessment_date = EXCLUDED.assessment_date,
            notes = EXCLUDED.notes,
            concerns = EXCLUDED.concerns,
            entered_by = EXCLUDED.entered_by,
            needs_review = EXCLUDED.needs_review,
            is_draft = EXCLUDED.is_draft,
            subject_area = EXCLUDED.subject_area
    ''', (student_id, assessment_type, assessment_period, school_year, score_value,
          score_normalized, assessment_date, notes, concerns, entered_by,
          int(needs_review), int(is_draft), subject_area))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Teacher notes
# ---------------------------------------------------------------------------

def add_teacher_note(student_id: int, note_text: str, tag: str = None,
                     note_date: str = None, created_by: str = 'Teacher'):
    """Add a teacher note with optional tag/date."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO teacher_notes (student_id, note_text, tag, note_date, created_by)
        VALUES (%s, %s, %s, %s, %s)
    ''', (student_id, note_text, tag, note_date, created_by))
    conn.commit()
    conn.close()


def get_teacher_notes(student_id: int) -> pd.DataFrame:
    """Get teacher notes for a student."""
    conn = get_db_connection()
    df = pd.read_sql_query(
        'SELECT * FROM teacher_notes WHERE student_id = %s ORDER BY COALESCE(note_date, created_at) DESC',
        conn, params=[student_id],
    )
    conn.close()
    return df

# ---------------------------------------------------------------------------
# Student goals
# ---------------------------------------------------------------------------

def upsert_student_goal(student_id: int, measure: str, baseline_score: float,
                        target_score: float, expected_weekly_growth: float,
                        start_date: str = None, target_date: str = None):
    """Create or update a goal for a student and measure."""
    conn = get_db_connection()
    cur = _dict_cursor(conn)
    cur.execute(
        'SELECT goal_id FROM student_goals WHERE student_id = %s AND measure = %s',
        (student_id, measure),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute('''
            UPDATE student_goals
            SET baseline_score = %s, target_score = %s, expected_weekly_growth = %s,
                start_date = %s, target_date = %s
            WHERE student_id = %s AND measure = %s
        ''', (baseline_score, target_score, expected_weekly_growth,
              start_date, target_date, student_id, measure))
    else:
        cur.execute('''
            INSERT INTO student_goals
                (student_id, measure, baseline_score, target_score, expected_weekly_growth, start_date, target_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (student_id, measure, baseline_score, target_score, expected_weekly_growth, start_date, target_date))
    conn.commit()
    conn.close()


def get_student_goals(student_id: int) -> pd.DataFrame:
    """Get all goals for a student."""
    conn = get_db_connection()
    df = pd.read_sql_query(
        'SELECT * FROM student_goals WHERE student_id = %s ORDER BY created_at DESC',
        conn, params=[student_id],
    )
    conn.close()
    return df

# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def add_intervention(student_id: int, intervention_type: str, start_date: str,
                     end_date: str = None, frequency: str = None, duration_minutes: int = None,
                     status: str = 'Active', notes: str = None):
    """Add an intervention record."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO interventions
            (student_id, intervention_type, start_date, end_date, frequency, duration_minutes, status, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (student_id, intervention_type, start_date, end_date, frequency, duration_minutes, status, notes))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Literacy scores
# ---------------------------------------------------------------------------

def save_literacy_score(student_id: int, school_year: str, assessment_period: str,
                        overall_score: float, reading_component: float = None,
                        phonics_component: float = None, spelling_component: float = None,
                        sight_words_component: float = None, risk_level: str = None,
                        trend: str = None):
    """Save calculated literacy score (upsert on unique constraint)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO literacy_scores
            (student_id, school_year, assessment_period, overall_literacy_score,
             reading_component, phonics_component, spelling_component, sight_words_component,
             risk_level, trend)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, school_year, assessment_period)
        DO UPDATE SET
            overall_literacy_score = EXCLUDED.overall_literacy_score,
            reading_component = EXCLUDED.reading_component,
            phonics_component = EXCLUDED.phonics_component,
            spelling_component = EXCLUDED.spelling_component,
            sight_words_component = EXCLUDED.sight_words_component,
            risk_level = EXCLUDED.risk_level,
            trend = EXCLUDED.trend,
            calculated_at = NOW()
    ''', (student_id, school_year, assessment_period, overall_score,
          reading_component, phonics_component, spelling_component, sight_words_component,
          risk_level, trend))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_all_students(grade_level: str = None, class_name: str = None,
                     teacher_name: str = None, school_year: str = None) -> pd.DataFrame:
    """Get all students with optional filters."""
    conn = get_db_connection()
    query = 'SELECT * FROM students WHERE 1=1'
    params: list = []

    if grade_level:
        query += ' AND grade_level = %s'
        params.append(grade_level)
    if class_name:
        query += ' AND class_name = %s'
        params.append(class_name)
    if teacher_name:
        query += ' AND teacher_name = %s'
        params.append(teacher_name)
    if school_year:
        query += ' AND school_year = %s'
        params.append(school_year)

    query += ' ORDER BY student_name, grade_level'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_student_assessments(student_id: int, school_year: str = None) -> pd.DataFrame:
    """Get all assessments for a student."""
    conn = get_db_connection()
    query = '''
        SELECT a.*, s.student_name, s.grade_level
        FROM assessments a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.student_id = %s
    '''
    params: list = [student_id]

    if school_year:
        query += ' AND a.school_year = %s'
        params.append(school_year)

    query += ' ORDER BY a.assessment_date DESC, a.assessment_period'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_student_interventions(student_id: int) -> pd.DataFrame:
    """Get all interventions for a student."""
    conn = get_db_connection()
    query = '''
        SELECT i.*, s.student_name
        FROM interventions i
        JOIN students s ON i.student_id = s.student_id
        WHERE i.student_id = %s
        ORDER BY i.start_date DESC
    '''
    df = pd.read_sql_query(query, conn, params=[student_id])
    conn.close()
    return df


def get_latest_literacy_score(student_id: int, school_year: str = None) -> Optional[Dict]:
    """Get the latest literacy score for a student."""
    conn = get_db_connection()
    query = 'SELECT * FROM literacy_scores WHERE student_id = %s'
    params: list = [student_id]

    if school_year:
        query += ' AND school_year = %s'
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
    cur = _dict_cursor(conn)
    cur.execute(query, params)
    result = cur.fetchone()
    conn.close()
    return dict(result) if result else None

# ---------------------------------------------------------------------------
# Math scores
# ---------------------------------------------------------------------------

def save_math_score(student_id: int, school_year: str, assessment_period: str,
                    overall_score: float, computation_component: float = None,
                    concepts_component: float = None, number_fluency_component: float = None,
                    quantity_discrimination_component: float = None, risk_level: str = None,
                    trend: str = None):
    """Save calculated math score (upsert on unique constraint)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO math_scores
            (student_id, school_year, assessment_period, overall_math_score,
             computation_component, concepts_component, number_fluency_component,
             quantity_discrimination_component, risk_level, trend)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, school_year, assessment_period)
        DO UPDATE SET
            overall_math_score = EXCLUDED.overall_math_score,
            computation_component = EXCLUDED.computation_component,
            concepts_component = EXCLUDED.concepts_component,
            number_fluency_component = EXCLUDED.number_fluency_component,
            quantity_discrimination_component = EXCLUDED.quantity_discrimination_component,
            risk_level = EXCLUDED.risk_level,
            trend = EXCLUDED.trend,
            calculated_at = NOW()
    ''', (student_id, school_year, assessment_period, overall_score,
          computation_component, concepts_component, number_fluency_component,
          quantity_discrimination_component, risk_level, trend))
    conn.commit()
    conn.close()


def get_latest_math_score(student_id: int, school_year: str = None) -> Optional[Dict]:
    """Get the latest math score for a student."""
    conn = get_db_connection()
    query = 'SELECT * FROM math_scores WHERE student_id = %s'
    params: list = [student_id]

    if school_year:
        query += ' AND school_year = %s'
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
    cur = _dict_cursor(conn)
    cur.execute(query, params)
    result = cur.fetchone()
    conn.close()
    return dict(result) if result else None


if __name__ == '__main__':
    init_database()
