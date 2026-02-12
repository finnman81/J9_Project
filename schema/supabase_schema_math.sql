-- =============================================================================
-- Database Migration: Add Math Assessment Support
-- Run this in the Supabase SQL Editor after the base schema
-- =============================================================================

-- Add subject_area column to assessments table
ALTER TABLE assessments 
ADD COLUMN IF NOT EXISTS subject_area TEXT DEFAULT 'Reading';

-- Create index on subject_area for performance
CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(subject_area);

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

-- Indexes for math_scores
CREATE INDEX IF NOT EXISTS idx_math_scores_student ON math_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_math_scores_year ON math_scores(school_year);
CREATE INDEX IF NOT EXISTS idx_math_scores_period ON math_scores(assessment_period);
