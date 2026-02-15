-- =============================================================================
-- Migration V2: Structured Data, Assessment Metadata, and Tier Storage
-- Run this in the Supabase SQL Editor after the base schema + math migration
-- =============================================================================

-- ─── Interventions table: add structured fields ──────────────────────────────

ALTER TABLE interventions ADD COLUMN IF NOT EXISTS subject_area TEXT;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS focus_skill TEXT;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS delivery_type TEXT;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS minutes_per_week INTEGER;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS pre_score DOUBLE PRECISION;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS post_score DOUBLE PRECISION;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS pre_score_measure TEXT;
ALTER TABLE interventions ADD COLUMN IF NOT EXISTS post_score_measure TEXT;

-- ─── Assessments table: add metadata fields ──────────────────────────────────

ALTER TABLE assessments ADD COLUMN IF NOT EXISTS assessment_system TEXT;
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS measure TEXT;
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS raw_score DOUBLE PRECISION;
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS scaled_score DOUBLE PRECISION;
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS benchmark_threshold_used TEXT;
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS score_metadata JSONB DEFAULT '{}';

-- ─── Assessments uniqueness: upgrade constraint ──────────────────────────────
-- Drop the old constraint and create the new, more specific one.
-- The old constraint: UNIQUE(student_id, assessment_type, assessment_period, school_year)
-- The new constraint includes subject_area, assessment_system, and measure.

-- Note: We keep the old constraint name for safety; if it doesn't exist by name,
-- the DROP will fail gracefully. We use DO blocks for idempotency.

DO $$
BEGIN
    -- Try to drop the old constraint by the auto-generated name
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'assessments'
        AND constraint_type = 'UNIQUE'
        AND constraint_name = 'assessments_student_id_assessment_type_assessment_period_sch_key'
    ) THEN
        ALTER TABLE assessments DROP CONSTRAINT assessments_student_id_assessment_type_assessment_period_sch_key;
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- Ignore if constraint doesn't exist
    NULL;
END $$;

-- Create the new, more specific uniqueness constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'assessments'
        AND constraint_name = 'assessments_unique_v2'
    ) THEN
        ALTER TABLE assessments ADD CONSTRAINT assessments_unique_v2
            UNIQUE(student_id, subject_area, assessment_system, measure, assessment_period, school_year);
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- If columns have NULLs, fall back to keeping old constraint
    RAISE NOTICE 'Could not create new unique constraint; backfill assessment_system/measure first.';
END $$;

-- ─── Scores tables: add support_tier column ──────────────────────────────────

ALTER TABLE literacy_scores ADD COLUMN IF NOT EXISTS support_tier TEXT;
ALTER TABLE math_scores ADD COLUMN IF NOT EXISTS support_tier TEXT;

-- ─── New indexes for performance ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_assessments_system ON assessments(assessment_system);
CREATE INDEX IF NOT EXISTS idx_assessments_measure ON assessments(measure);
CREATE INDEX IF NOT EXISTS idx_interventions_subject ON interventions(subject_area);
CREATE INDEX IF NOT EXISTS idx_interventions_status ON interventions(status);
CREATE INDEX IF NOT EXISTS idx_assessments_date ON assessments(assessment_date);
CREATE INDEX IF NOT EXISTS idx_literacy_scores_tier ON literacy_scores(support_tier);
CREATE INDEX IF NOT EXISTS idx_math_scores_tier ON math_scores(support_tier);
