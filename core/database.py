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

    Uses DATABASE_URL from environment first (for API/CLI). If unset, tries
    Streamlit secrets (for Streamlit app). This allows the API to run without
    Streamlit installed.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        try:
            import streamlit as st
            db_url = st.secrets.get("DATABASE_URL") or st.secrets["DATABASE_URL"]
        except Exception:
            pass
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL not found. Set it as an environment variable "
            "or in .streamlit/secrets.toml for Streamlit."
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
            assessment_system TEXT,
            measure TEXT,
            raw_score DOUBLE PRECISION,
            scaled_score DOUBLE PRECISION,
            benchmark_threshold_used TEXT,
            score_metadata JSONB DEFAULT '{}',
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
            subject_area TEXT,
            focus_skill TEXT,
            delivery_type TEXT,
            minutes_per_week INTEGER,
            pre_score DOUBLE PRECISION,
            post_score DOUBLE PRECISION,
            pre_score_measure TEXT,
            post_score_measure TEXT,
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
            support_tier TEXT,
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
            support_tier TEXT,
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
                   subject_area: str = 'Reading',
                   assessment_system: str = None, measure: str = None,
                   raw_score: float = None, scaled_score: float = None,
                   benchmark_threshold_used: str = None, score_metadata: dict = None):
    """Add an assessment record (upsert on unique constraint)."""
    import json
    meta_json = json.dumps(score_metadata) if score_metadata else '{}'
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO assessments
            (student_id, assessment_type, assessment_period, school_year, score_value,
             score_normalized, assessment_date, notes, concerns, entered_by,
             needs_review, is_draft, subject_area,
             assessment_system, measure, raw_score, scaled_score,
             benchmark_threshold_used, score_metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            subject_area = EXCLUDED.subject_area,
            assessment_system = EXCLUDED.assessment_system,
            measure = EXCLUDED.measure,
            raw_score = EXCLUDED.raw_score,
            scaled_score = EXCLUDED.scaled_score,
            benchmark_threshold_used = EXCLUDED.benchmark_threshold_used,
            score_metadata = EXCLUDED.score_metadata
    ''', (student_id, assessment_type, assessment_period, school_year, score_value,
          score_normalized, assessment_date, notes, concerns, entered_by,
          int(needs_review), int(is_draft), subject_area,
          assessment_system, measure, raw_score, scaled_score,
          benchmark_threshold_used, meta_json))
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


def get_enrollment_notes(enrollment_id: str) -> pd.DataFrame:
    """Get teacher notes for an enrollment (by enrollment_id; fallback legacy_student_id)."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(
            'SELECT * FROM teacher_notes WHERE enrollment_id = %s ORDER BY COALESCE(note_date, created_at) DESC',
            conn, params=[enrollment_id],
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        en = get_enrollment(enrollment_id)
        if en and en.get("legacy_student_id") is not None:
            return get_teacher_notes(int(en["legacy_student_id"]))
    return df


def get_enrollment_goals(enrollment_id: str) -> pd.DataFrame:
    """Get goals for an enrollment (by enrollment_id; fallback legacy_student_id)."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(
            'SELECT * FROM student_goals WHERE enrollment_id = %s ORDER BY created_at DESC',
            conn, params=[enrollment_id],
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        en = get_enrollment(enrollment_id)
        if en and en.get("legacy_student_id") is not None:
            return get_student_goals(int(en["legacy_student_id"]))
    return df

# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def add_intervention(student_id: int, intervention_type: str, start_date: str,
                     end_date: str = None, frequency: str = None, duration_minutes: int = None,
                     status: str = 'Active', notes: str = None,
                     subject_area: str = None, focus_skill: str = None,
                     delivery_type: str = None, minutes_per_week: int = None,
                     pre_score: float = None, post_score: float = None,
                     pre_score_measure: str = None, post_score_measure: str = None):
    """Add an intervention record with optional structured fields."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO interventions
            (student_id, intervention_type, start_date, end_date, frequency,
             duration_minutes, status, notes, subject_area, focus_skill,
             delivery_type, minutes_per_week, pre_score, post_score,
             pre_score_measure, post_score_measure)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (student_id, intervention_type, start_date, end_date, frequency,
          duration_minutes, status, notes, subject_area, focus_skill,
          delivery_type, minutes_per_week, pre_score, post_score,
          pre_score_measure, post_score_measure))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Literacy scores
# ---------------------------------------------------------------------------

def save_literacy_score(student_id: int, school_year: str, assessment_period: str,
                        overall_score: float, reading_component: float = None,
                        phonics_component: float = None, spelling_component: float = None,
                        sight_words_component: float = None, risk_level: str = None,
                        trend: str = None, support_tier: str = None):
    """Save calculated literacy score (upsert on unique constraint)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO literacy_scores
            (student_id, school_year, assessment_period, overall_literacy_score,
             reading_component, phonics_component, spelling_component, sight_words_component,
             risk_level, trend, support_tier)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, school_year, assessment_period)
        DO UPDATE SET
            overall_literacy_score = EXCLUDED.overall_literacy_score,
            reading_component = EXCLUDED.reading_component,
            phonics_component = EXCLUDED.phonics_component,
            spelling_component = EXCLUDED.spelling_component,
            sight_words_component = EXCLUDED.sight_words_component,
            risk_level = EXCLUDED.risk_level,
            trend = EXCLUDED.trend,
            support_tier = EXCLUDED.support_tier,
            calculated_at = NOW()
    ''', (student_id, school_year, assessment_period, overall_score,
          reading_component, phonics_component, spelling_component, sight_words_component,
          risk_level, trend, support_tier))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_all_students(grade_level: str = None, class_name: str = None,
                     teacher_name: str = None, school_year: str = None) -> pd.DataFrame:
    """Get all students with optional filters. Legacy: reads from students table."""
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


def get_legacy_student_uuids(legacy_student_ids: List[int]) -> Dict[int, str]:
    """Return mapping legacy_student_id -> student_uuid from student_id_map."""
    if not legacy_student_ids:
        return {}
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(legacy_student_ids))
    query = f"SELECT legacy_student_id, student_uuid FROM student_id_map WHERE legacy_student_id IN ({placeholders})"
    try:
        df = pd.read_sql_query(query, conn, params=legacy_student_ids)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        return {}
    return dict(zip(df["legacy_student_id"].astype(int), df["student_uuid"].astype(str)))


# ---------------------------------------------------------------------------
# Enrollment-based helpers (students_core + student_enrollments)
# Use these for dashboard and detail views; legacy scores/interventions via legacy_student_id.
# ---------------------------------------------------------------------------

def _enrollment_base_query(extra_select: str = ""):
    """Base query: student_enrollments JOIN students_core, resolve legacy_student_id from student_id_map."""
    return f"""
        SELECT e.enrollment_id, e.student_uuid, c.display_name, e.school_year, e.grade_level,
               e.class_name, e.teacher_name
               {extra_select}
        FROM student_enrollments e
        JOIN students_core c ON c.student_uuid = e.student_uuid
        LEFT JOIN LATERAL (
            SELECT legacy_student_id FROM student_id_map m WHERE m.student_uuid = e.student_uuid LIMIT 1
        ) m ON true
    """.strip()


def get_all_enrollments(grade_level: str = None, class_name: str = None,
                        teacher_name: str = None, school_year: str = None) -> pd.DataFrame:
    """Get all enrollments with optional filters. Returns enrollment_id, display_name, grade_level, class_name, teacher_name, school_year, legacy_student_id."""
    conn = get_db_connection()
    extra = ", m.legacy_student_id"
    query = _enrollment_base_query(extra) + " WHERE 1=1"
    params: list = []
    if grade_level:
        query += " AND e.grade_level = %s"
        params.append(grade_level)
    if class_name:
        query += " AND e.class_name = %s"
        params.append(class_name)
    if teacher_name:
        query += " AND e.teacher_name = %s"
        params.append(teacher_name)
    if school_year:
        query += " AND e.school_year = %s"
        params.append(school_year)
    query += " ORDER BY c.display_name, e.grade_level, e.school_year"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()
    return df


def get_enrollment(enrollment_id: str):
    """Get one enrollment by UUID with display_name and legacy_student_id. Returns dict or None."""
    conn = get_db_connection()
    cur = _dict_cursor(conn)
    extra = ", m.legacy_student_id"
    query = _enrollment_base_query(extra) + " WHERE e.enrollment_id = %s"
    try:
        cur.execute(query, (enrollment_id,))
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    return dict(row) if row else None


def get_enrollment_assessments(enrollment_id: str, school_year: str = None) -> pd.DataFrame:
    """Get assessments for an enrollment (by enrollment_id). Falls back to legacy student_id if enrollment_id column missing."""
    conn = get_db_connection()
    params: list = [enrollment_id]
    query = """
        SELECT a.*, e.grade_level
        FROM assessments a
        LEFT JOIN student_enrollments e ON e.enrollment_id = a.enrollment_id
        WHERE a.enrollment_id = %s
    """
    if school_year:
        query += " AND a.school_year = %s"
        params.append(school_year)
    query += " ORDER BY a.assessment_date DESC NULLS LAST, a.assessment_period"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty and get_enrollment(enrollment_id):
        en = get_enrollment(enrollment_id)
        leg_id = en.get("legacy_student_id")
        if leg_id is not None:
            df = get_student_assessments(int(leg_id), school_year=school_year)
    return df


def get_enrollment_interventions(enrollment_id: str) -> pd.DataFrame:
    """Get interventions for this enrollment (by enrollment_id first, then legacy student_id fallback)."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(
            '''SELECT i.* FROM interventions i
               WHERE i.enrollment_id = %s
               ORDER BY i.start_date DESC NULLS LAST''',
            conn, params=[enrollment_id],
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty:
        return df
    en = get_enrollment(enrollment_id)
    if not en or en.get("legacy_student_id") is None:
        return pd.DataFrame()
    return get_student_interventions(int(en["legacy_student_id"]))


def get_latest_literacy_score_for_enrollment(enrollment_id: str, school_year: str = None) -> Optional[Dict]:
    """Latest literacy score for this enrollment's context (via legacy_student_id)."""
    en = get_enrollment(enrollment_id)
    if not en or en.get("legacy_student_id") is None:
        return None
    return get_latest_literacy_score(int(en["legacy_student_id"]), school_year=school_year)


def get_latest_math_score_for_enrollment(enrollment_id: str, school_year: str = None) -> Optional[Dict]:
    """Latest math score for this enrollment's context (via legacy_student_id)."""
    en = get_enrollment(enrollment_id)
    if not en or en.get("legacy_student_id") is None:
        return None
    return get_latest_math_score(int(en["legacy_student_id"]), school_year=school_year)


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
                    trend: str = None, support_tier: str = None):
    """Save calculated math score (upsert on unique constraint)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO math_scores
            (student_id, school_year, assessment_period, overall_math_score,
             computation_component, concepts_component, number_fluency_component,
             quantity_discrimination_component, risk_level, trend, support_tier)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (student_id, school_year, assessment_period)
        DO UPDATE SET
            overall_math_score = EXCLUDED.overall_math_score,
            computation_component = EXCLUDED.computation_component,
            concepts_component = EXCLUDED.concepts_component,
            number_fluency_component = EXCLUDED.number_fluency_component,
            quantity_discrimination_component = EXCLUDED.quantity_discrimination_component,
            risk_level = EXCLUDED.risk_level,
            trend = EXCLUDED.trend,
            support_tier = EXCLUDED.support_tier,
            calculated_at = NOW()
    ''', (student_id, school_year, assessment_period, overall_score,
          computation_component, concepts_component, number_fluency_component,
          quantity_discrimination_component, risk_level, trend, support_tier))
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


# ---------------------------------------------------------------------------
# Active interventions helper
# ---------------------------------------------------------------------------

def get_active_interventions(student_id: int = None, subject: str = None) -> pd.DataFrame:
    """Get active interventions, optionally filtered by student and/or subject."""
    conn = get_db_connection()
    query = "SELECT i.*, s.student_name, s.grade_level, s.teacher_name FROM interventions i JOIN students s ON i.student_id = s.student_id WHERE i.status = 'Active'"
    params: list = []

    if student_id:
        query += ' AND i.student_id = %s'
        params.append(student_id)
    if subject:
        query += ' AND (i.subject_area = %s OR i.subject_area IS NULL)'
        params.append(subject)

    query += ' ORDER BY i.start_date DESC'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_all_interventions(school_year: str = None) -> pd.DataFrame:
    """Get all interventions with student info."""
    conn = get_db_connection()
    query = '''
        SELECT i.*, s.student_name, s.grade_level, s.teacher_name, s.school_year
        FROM interventions i
        JOIN students s ON i.student_id = s.student_id
    '''
    params: list = []
    if school_year:
        query += ' WHERE s.school_year = %s'
        params.append(school_year)
    query += ' ORDER BY i.start_date DESC'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_all_assessments(subject: str = None, school_year: str = None,
                        exclude_drafts: bool = True) -> pd.DataFrame:
    """Get all assessments with student info, optionally filtered."""
    conn = get_db_connection()
    query = '''
        SELECT a.*, s.student_name, s.grade_level, s.teacher_name
        FROM assessments a
        JOIN students s ON a.student_id = s.student_id
        WHERE 1=1
    '''
    params: list = []
    if subject:
        query += ' AND a.subject_area = %s'
        params.append(subject)
    if school_year:
        query += ' AND a.school_year = %s'
        params.append(school_year)
    if exclude_drafts:
        query += ' AND COALESCE(a.is_draft, 0) = 0'

    query += ' ORDER BY a.assessment_date DESC NULLS LAST, a.created_at DESC'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_all_scores(subject: str = 'Reading', school_year: str = None) -> pd.DataFrame:
    """Get all calculated scores for a subject."""
    conn = get_db_connection()
    table = 'literacy_scores' if subject == 'Reading' else 'math_scores'
    query = f'SELECT sc.*, s.student_name, s.grade_level, s.teacher_name FROM {table} sc JOIN students s ON sc.student_id = s.student_id'
    params: list = []
    if school_year:
        query += ' WHERE sc.school_year = %s'
        params.append(school_year)
    query += ' ORDER BY sc.student_id, sc.assessment_period'
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Teacher-first analytics views (v_support_status, v_priority_students, etc.)
# Require migration_v3 + students_core/student_enrollments.
# ---------------------------------------------------------------------------

def get_v_support_status(
    teacher_name: str = None,
    school_year: str = None,
    subject_area: str = None,
    grade_level: str = None,
    class_name: str = None,
) -> pd.DataFrame:
    """Query v_support_status with optional filters."""
    conn = get_db_connection()
    query = "SELECT * FROM public.v_support_status WHERE 1=1"
    params: list = []
    if teacher_name:
        query += " AND teacher_name = %s"
        params.append(teacher_name)
    if school_year:
        query += " AND school_year = %s"
        params.append(school_year)
    if subject_area:
        query += " AND subject_area = %s"
        params.append(subject_area)
    if grade_level:
        query += " AND grade_level = %s"
        params.append(grade_level)
    if class_name:
        query += " AND class_name = %s"
        params.append(class_name)
    query += " ORDER BY display_name, subject_area"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_v_priority_students(
    teacher_name: str = None,
    school_year: str = None,
    subject_area: str = None,
    grade_level: str = None,
    class_name: str = None,
) -> pd.DataFrame:
    """Query v_priority_students with optional filters."""
    conn = get_db_connection()
    query = "SELECT * FROM public.v_priority_students WHERE 1=1"
    params: list = []
    if teacher_name:
        query += " AND teacher_name = %s"
        params.append(teacher_name)
    if school_year:
        query += " AND school_year = %s"
        params.append(school_year)
    if subject_area:
        query += " AND subject_area = %s"
        params.append(subject_area)
    if grade_level:
        query += " AND grade_level = %s"
        params.append(grade_level)
    if class_name:
        query += " AND class_name = %s"
        params.append(class_name)
    query += " ORDER BY priority_score DESC NULLS LAST, display_name"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_v_growth_last_two(
    teacher_name: str = None,
    school_year: str = None,
    subject_area: str = None,
    grade_level: str = None,
    class_name: str = None,
) -> pd.DataFrame:
    """Query v_growth_last_two joined to enrollments for filtering."""
    conn = get_db_connection()
    query = """
        SELECT g.*
        FROM public.v_growth_last_two g
        JOIN public.student_enrollments e ON e.enrollment_id = g.enrollment_id
        WHERE 1=1
    """
    params: list = []
    if teacher_name:
        query += " AND e.teacher_name = %s"
        params.append(teacher_name)
    if school_year:
        query += " AND g.school_year = %s"
        params.append(school_year)
    if subject_area:
        query += " AND g.subject_area = %s"
        params.append(subject_area)
    if grade_level:
        query += " AND e.grade_level = %s"
        params.append(grade_level)
    if class_name:
        query += " AND e.class_name = %s"
        params.append(class_name)
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_enrollment_support_status(enrollment_id: str, subject_area: str) -> Optional[Dict]:
    """One row from v_support_status for this enrollment + subject (for detail header KPIs)."""
    conn = get_db_connection()
    query = "SELECT * FROM public.v_support_status WHERE enrollment_id = %s AND subject_area = %s LIMIT 1"
    try:
        cur = _dict_cursor(conn)
        cur.execute(query, (enrollment_id, subject_area))
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    return dict(row) if row else None


def get_enrollment_growth(enrollment_id: str, subject_area: str, school_year: str = None) -> Optional[Dict]:
    """One row from v_growth_last_two for this enrollment + subject (for trend)."""
    conn = get_db_connection()
    query = "SELECT * FROM public.v_growth_last_two WHERE enrollment_id = %s AND subject_area = %s"
    params: list = [enrollment_id, subject_area]
    if school_year:
        query += " AND school_year = %s"
        params.append(school_year)
    query += " LIMIT 1"
    try:
        cur = _dict_cursor(conn)
        cur.execute(query, params)
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    return dict(row) if row else None


def get_benchmark_thresholds(
    subject_area: str = None,
    grade_level: str = None,
    school_year: str = None,
) -> pd.DataFrame:
    """Get benchmark_thresholds for distribution reference lines."""
    conn = get_db_connection()
    query = "SELECT * FROM public.benchmark_thresholds WHERE 1=1"
    params: list = []
    if subject_area:
        query += " AND subject_area = %s"
        params.append(subject_area)
    if grade_level:
        query += " AND grade_level = %s"
        params.append(grade_level)
    if school_year:
        query += " AND school_year = %s"
        params.append(school_year)
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Multi-enrollment aggregation (student-uuid level)
# ---------------------------------------------------------------------------

def get_enrollments_for_student_uuid(student_uuid: str) -> pd.DataFrame:
    """All enrollments for a given student_uuid, ordered by school_year DESC, grade_level."""
    conn = get_db_connection()
    query = """
        SELECT e.enrollment_id, e.student_uuid, c.display_name, e.school_year, e.grade_level,
               e.class_name, e.teacher_name
        FROM student_enrollments e
        JOIN students_core c ON c.student_uuid = e.student_uuid
        WHERE e.student_uuid = %s
        ORDER BY e.school_year DESC, e.grade_level
    """
    try:
        df = pd.read_sql_query(query, conn, params=[student_uuid])
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_multi_enrollment_assessments(enrollment_ids: List[str], subject_area: str = None, school_year: str = None) -> pd.DataFrame:
    """Get assessments across multiple enrollment_ids, with optional subject/year filter."""
    if not enrollment_ids:
        return pd.DataFrame()
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    query = f"""
        SELECT a.*, e.grade_level AS enrollment_grade, e.school_year AS enrollment_year
        FROM assessments a
        LEFT JOIN student_enrollments e ON e.enrollment_id = a.enrollment_id
        WHERE a.enrollment_id::text IN ({placeholders})
    """
    params: list = list(enrollment_ids)
    if subject_area:
        query += " AND a.subject_area = %s"
        params.append(subject_area)
    if school_year:
        query += " AND a.school_year = %s"
        params.append(school_year)
    query += " ORDER BY a.assessment_date DESC NULLS LAST, a.school_year DESC, a.assessment_period"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_multi_enrollment_interventions(enrollment_ids: List[str]) -> pd.DataFrame:
    """Get interventions across multiple enrollment_ids."""
    if not enrollment_ids:
        return pd.DataFrame()
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    query = f"""
        SELECT i.*
        FROM interventions i
        WHERE i.enrollment_id::text IN ({placeholders})
        ORDER BY i.start_date DESC NULLS LAST
    """
    try:
        df = pd.read_sql_query(query, conn, params=enrollment_ids)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        # Fallback: try via legacy student_id from any of the enrollments
        for eid in enrollment_ids:
            en = get_enrollment(eid)
            if en and en.get("legacy_student_id") is not None:
                return get_student_interventions(int(en["legacy_student_id"]))
    return df


def get_multi_enrollment_notes(enrollment_ids: List[str]) -> pd.DataFrame:
    """Get notes across multiple enrollment_ids."""
    if not enrollment_ids:
        return pd.DataFrame()
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM teacher_notes WHERE enrollment_id::text IN ({placeholders}) ORDER BY COALESCE(note_date, created_at) DESC",
            conn, params=enrollment_ids,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        # Fallback via legacy student_id
        for eid in enrollment_ids:
            en = get_enrollment(eid)
            if en and en.get("legacy_student_id") is not None:
                return get_teacher_notes(int(en["legacy_student_id"]))
    return df


def get_multi_enrollment_goals(enrollment_ids: List[str]) -> pd.DataFrame:
    """Get goals across multiple enrollment_ids."""
    if not enrollment_ids:
        return pd.DataFrame()
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM student_goals WHERE enrollment_id::text IN ({placeholders}) ORDER BY created_at DESC",
            conn, params=enrollment_ids,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        for eid in enrollment_ids:
            en = get_enrollment(eid)
            if en and en.get("legacy_student_id") is not None:
                return get_student_goals(int(en["legacy_student_id"]))
    return df


def get_multi_enrollment_support_status(enrollment_ids: List[str], subject_area: str) -> Optional[Dict]:
    """Best support status across multiple enrollment_ids (picks the one with a latest_score)."""
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    query = f"""
        SELECT * FROM public.v_support_status
        WHERE enrollment_id::text IN ({placeholders}) AND subject_area = %s
        ORDER BY latest_date DESC NULLS LAST
        LIMIT 1
    """
    params = list(enrollment_ids) + [subject_area]
    try:
        cur = _dict_cursor(conn)
        cur.execute(query, params)
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    return dict(row) if row else None


def get_multi_enrollment_growth(enrollment_ids: List[str], subject_area: str) -> Optional[Dict]:
    """Best growth data across multiple enrollment_ids."""
    conn = get_db_connection()
    placeholders = ','.join(['%s'] * len(enrollment_ids))
    query = f"""
        SELECT * FROM public.v_growth_last_two
        WHERE enrollment_id::text IN ({placeholders}) AND subject_area = %s
        LIMIT 1
    """
    params = list(enrollment_ids) + [subject_area]
    try:
        cur = _dict_cursor(conn)
        cur.execute(query, params)
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    return dict(row) if row else None


if __name__ == '__main__':
    init_database()
