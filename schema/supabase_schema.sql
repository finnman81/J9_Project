-- =============================================================================
-- Supabase PostgreSQL Schema for Literacy Assessment System
-- Run this in the Supabase SQL Editor (https://supabase.com/dashboard)
-- =============================================================================

-- Students table
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
);

-- Assessments table
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
);

-- Interventions table
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
);

-- Literacy scores table (calculated/denormalized)
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
);

-- Teacher notes table
CREATE TABLE IF NOT EXISTS teacher_notes (
    note_id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    note_text TEXT NOT NULL,
    tag TEXT,
    note_date DATE,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Student goals table
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
);

-- Math scores table (calculated/denormalized)
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
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade_level);
CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name);
CREATE INDEX IF NOT EXISTS idx_students_teacher ON students(teacher_name);
CREATE INDEX IF NOT EXISTS idx_students_year ON students(school_year);
CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id);
CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(assessment_type);
CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(subject_area);
CREATE INDEX IF NOT EXISTS idx_interventions_student ON interventions(student_id);
CREATE INDEX IF NOT EXISTS idx_literacy_scores_student ON literacy_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_math_scores_student ON math_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_math_scores_year ON math_scores(school_year);
CREATE INDEX IF NOT EXISTS idx_math_scores_period ON math_scores(assessment_period);
CREATE INDEX IF NOT EXISTS idx_teacher_notes_student ON teacher_notes(student_id);
CREATE INDEX IF NOT EXISTS idx_student_goals_student ON student_goals(student_id);
