-- =============================================================================
-- Migration V3: Teacher-First Dashboard (enrollment_id, effective_date, views)
-- Run after base schema + enrollment identity (students_core, student_enrollments,
-- student_id_map, assessments.enrollment_id). Safe to run idempotently.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1.1 Add enrollment_id to remaining workflow tables
-- -----------------------------------------------------------------------------
ALTER TABLE public.interventions ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES public.student_enrollments(enrollment_id);
ALTER TABLE public.teacher_notes ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES public.student_enrollments(enrollment_id);
ALTER TABLE public.student_goals ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES public.student_enrollments(enrollment_id);

-- Backfill: match by legacy student_id -> student_uuid -> one enrollment (latest school_year)
-- Interventions (no school_year on table; pick latest enrollment per student)
UPDATE public.interventions i
SET enrollment_id = sub.enrollment_id
FROM (
  SELECT i2.intervention_id, e.enrollment_id,
         ROW_NUMBER() OVER (PARTITION BY i2.intervention_id ORDER BY e.school_year DESC NULLS LAST) AS rn
  FROM public.interventions i2
  JOIN public.student_id_map m ON m.legacy_student_id = i2.student_id
  JOIN public.student_enrollments e ON e.student_uuid = m.student_uuid
  WHERE i2.enrollment_id IS NULL
) sub
WHERE sub.intervention_id = i.intervention_id AND sub.rn = 1 AND i.enrollment_id IS NULL;

-- Teacher notes (no school_year on table)
UPDATE public.teacher_notes n
SET enrollment_id = sub.enrollment_id
FROM (
  SELECT n2.note_id, e.enrollment_id,
         ROW_NUMBER() OVER (PARTITION BY n2.note_id ORDER BY e.school_year DESC NULLS LAST) AS rn
  FROM public.teacher_notes n2
  JOIN public.student_id_map m ON m.legacy_student_id = n2.student_id
  JOIN public.student_enrollments e ON e.student_uuid = m.student_uuid
  WHERE n2.enrollment_id IS NULL
) sub
WHERE sub.note_id = n.note_id AND sub.rn = 1 AND n.enrollment_id IS NULL;

-- Student goals (no school_year on table)
UPDATE public.student_goals g
SET enrollment_id = sub.enrollment_id
FROM (
  SELECT g2.goal_id, e.enrollment_id,
         ROW_NUMBER() OVER (PARTITION BY g2.goal_id ORDER BY e.school_year DESC NULLS LAST) AS rn
  FROM public.student_goals g2
  JOIN public.student_id_map m ON m.legacy_student_id = g2.student_id
  JOIN public.student_enrollments e ON e.student_uuid = m.student_uuid
  WHERE g2.enrollment_id IS NULL
) sub
WHERE sub.goal_id = g.goal_id AND sub.rn = 1 AND g.enrollment_id IS NULL;

-- -----------------------------------------------------------------------------
-- 1.2 Assessment date/period helpers (overdue + growth)
-- -----------------------------------------------------------------------------
ALTER TABLE public.assessments ADD COLUMN IF NOT EXISTS effective_date DATE;
UPDATE public.assessments
SET effective_date = COALESCE(assessment_date::date, created_at::date)
WHERE effective_date IS NULL;

ALTER TABLE public.assessments ADD COLUMN IF NOT EXISTS period_order INT;
UPDATE public.assessments
SET period_order = CASE LOWER(TRIM(assessment_period))
  WHEN 'fall' THEN 1
  WHEN 'winter' THEN 2
  WHEN 'spring' THEN 3
  WHEN 'eoy' THEN 4
  ELSE NULL
END
WHERE period_order IS NULL;

-- -----------------------------------------------------------------------------
-- 1.3 New reference tables
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.benchmark_thresholds (
  threshold_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_area TEXT NOT NULL,
  assessment_type TEXT NOT NULL,
  grade_level TEXT NOT NULL,
  assessment_period TEXT NOT NULL,
  school_year TEXT NOT NULL,
  support_threshold NUMERIC,
  benchmark_threshold NUMERIC,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.assessment_definitions (
  assessment_def_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_area TEXT NOT NULL,
  assessment_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  score_scale TEXT,
  min_score NUMERIC,
  max_score NUMERIC,
  higher_is_better BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(subject_area, assessment_type)
);

CREATE TABLE IF NOT EXISTS public.norm_reference (
  norm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_system TEXT NOT NULL,
  subject_area TEXT NOT NULL,
  subtest TEXT NOT NULL,
  grade_level TEXT NOT NULL,
  assessment_period TEXT,
  norm_avg_stanine NUMERIC,
  norm_avg_pct NUMERIC,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(assessment_system, subject_area, subtest, grade_level, assessment_period)
);

-- Optional: score_rules for parsing weird score_value formats
CREATE TABLE IF NOT EXISTS public.score_rules (
  rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_area TEXT NOT NULL,
  assessment_type TEXT NOT NULL,
  rule_type TEXT NOT NULL,
  rule_config JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 1.4 & 1.5 Indexes and unique constraint (assessments may already have enrollment_id)
-- -----------------------------------------------------------------------------
ALTER TABLE public.assessments ADD COLUMN IF NOT EXISTS enrollment_id UUID REFERENCES public.student_enrollments(enrollment_id);

CREATE INDEX IF NOT EXISTS idx_assessments_enrollment_subject_date
ON public.assessments(enrollment_id, subject_area, effective_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_assessments_enrollment_year_period
ON public.assessments(enrollment_id, school_year, assessment_period);

CREATE INDEX IF NOT EXISTS idx_enrollments_teacher_year
ON public.student_enrollments(teacher_name, school_year);

CREATE INDEX IF NOT EXISTS idx_interventions_enrollment_status
ON public.interventions(enrollment_id, status);

CREATE INDEX IF NOT EXISTS idx_notes_enrollment
ON public.teacher_notes(enrollment_id);

CREATE INDEX IF NOT EXISTS idx_goals_enrollment
ON public.student_goals(enrollment_id);

-- Deduplicate assessments by (enrollment_id, subject_area, assessment_type, assessment_period, school_year)
-- Keep the row with the largest assessment_id (most recent insert); delete the rest.
DELETE FROM public.assessments a
USING public.assessments a2
WHERE a.enrollment_id IS NOT NULL
  AND a.enrollment_id = a2.enrollment_id
  AND a.subject_area IS NOT DISTINCT FROM a2.subject_area
  AND a.assessment_type = a2.assessment_type
  AND a.assessment_period = a2.assessment_period
  AND a.school_year = a2.school_year
  AND a.assessment_id < a2.assessment_id;

-- Prevent duplicate assessment in same window (only where enrollment_id is set)
DROP INDEX IF EXISTS public.uq_assessment_unique_window;
CREATE UNIQUE INDEX uq_assessment_unique_window
ON public.assessments(enrollment_id, subject_area, assessment_type, assessment_period, school_year)
WHERE enrollment_id IS NOT NULL;

-- =============================================================================
-- Phase 2: SQL Analytics Views
-- =============================================================================

-- 2.1 v_teacher_roster: one row per enrollment + subject with latest assessment
CREATE OR REPLACE VIEW public.v_teacher_roster AS
WITH latest AS (
  SELECT DISTINCT ON (a.enrollment_id, a.subject_area)
    a.enrollment_id,
    a.subject_area,
    a.score_normalized AS latest_score,
    a.effective_date AS latest_date,
    a.assessment_period AS latest_period,
    a.school_year,
    a.assessment_type AS latest_type
  FROM public.assessments a
  WHERE a.enrollment_id IS NOT NULL
  ORDER BY a.enrollment_id, a.subject_area, a.effective_date DESC NULLS LAST, a.created_at DESC
),
active_intervention AS (
  SELECT
    enrollment_id,
    TRUE AS has_active_intervention
  FROM public.interventions
  WHERE enrollment_id IS NOT NULL
    AND (status IS NULL OR LOWER(TRIM(status)) IN ('active', 'in progress', 'ongoing'))
  GROUP BY enrollment_id
)
SELECT
  e.enrollment_id,
  e.student_uuid,
  s.display_name,
  e.school_year,
  e.grade_level,
  e.class_name,
  e.teacher_name,
  l.subject_area,
  l.latest_score,
  l.latest_date,
  l.latest_period,
  l.latest_type,
  (CURRENT_DATE - l.latest_date)::INT AS days_since_assessment,
  COALESCE(ai.has_active_intervention, FALSE) AS has_active_intervention
FROM public.student_enrollments e
JOIN public.students_core s ON s.student_uuid = e.student_uuid
LEFT JOIN latest l ON l.enrollment_id = e.enrollment_id AND l.school_year = e.school_year
LEFT JOIN active_intervention ai ON ai.enrollment_id = e.enrollment_id;

-- 2.2 v_support_status: roster + tier from benchmark_thresholds
CREATE OR REPLACE VIEW public.v_support_status AS
SELECT
  r.enrollment_id,
  r.student_uuid,
  r.display_name,
  r.school_year,
  r.grade_level,
  r.class_name,
  r.teacher_name,
  r.subject_area,
  r.latest_score,
  r.latest_date,
  r.latest_period,
  r.days_since_assessment,
  r.has_active_intervention,
  t.support_threshold,
  t.benchmark_threshold,
  CASE
    WHEN r.latest_score IS NULL THEN 'Unknown'
    WHEN t.support_threshold IS NOT NULL AND r.latest_score < t.support_threshold THEN 'Needs Support'
    WHEN t.benchmark_threshold IS NOT NULL AND r.latest_score < t.benchmark_threshold THEN 'Monitor'
    ELSE 'On Track'
  END AS support_status,
  CASE
    WHEN r.latest_score IS NULL THEN 'Unknown'
    WHEN t.support_threshold IS NOT NULL AND r.latest_score < t.support_threshold THEN 'Intensive'
    WHEN t.benchmark_threshold IS NOT NULL AND r.latest_score < t.benchmark_threshold THEN 'Strategic'
    ELSE 'Core'
  END AS tier
FROM public.v_teacher_roster r
LEFT JOIN public.benchmark_thresholds t
  ON t.subject_area = r.subject_area
 AND t.assessment_type = r.latest_type
 AND t.grade_level = r.grade_level
 AND t.assessment_period = r.latest_period
 AND t.school_year = r.school_year;

-- 2.3 v_teacher_kpis: one row per teacher/year/subject
CREATE OR REPLACE VIEW public.v_teacher_kpis AS
SELECT
  teacher_name,
  school_year,
  subject_area,
  COUNT(*)::INT AS total_students,
  COUNT(*) FILTER (WHERE latest_score IS NOT NULL)::INT AS assessed_students,
  ROUND(100.0 * COUNT(*) FILTER (WHERE latest_score IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS assessed_pct,
  COUNT(*) FILTER (WHERE days_since_assessment > 90)::INT AS overdue_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE days_since_assessment > 90) / NULLIF(COUNT(*), 0), 1) AS overdue_pct,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_since_assessment)
    FILTER (WHERE days_since_assessment IS NOT NULL) AS median_days_since
FROM public.v_teacher_roster
GROUP BY teacher_name, school_year, subject_area;

-- 2.4 v_growth_last_two: growth between last two assessments per enrollment+subject+year
CREATE OR REPLACE VIEW public.v_growth_last_two AS
WITH ranked AS (
  SELECT
    a.enrollment_id,
    a.subject_area,
    a.school_year,
    a.effective_date,
    a.score_normalized,
    a.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY a.enrollment_id, a.subject_area, a.school_year
      ORDER BY a.effective_date DESC NULLS LAST, a.created_at DESC
    ) AS rn
  FROM public.assessments a
  WHERE a.enrollment_id IS NOT NULL AND a.score_normalized IS NOT NULL
),
pairs AS (
  SELECT
    enrollment_id,
    subject_area,
    school_year,
    MAX(score_normalized) FILTER (WHERE rn = 1) AS latest_score,
    MAX(score_normalized) FILTER (WHERE rn = 2) AS prior_score
  FROM ranked
  WHERE rn <= 2
  GROUP BY 1, 2, 3
)
SELECT
  p.enrollment_id,
  p.subject_area,
  p.school_year,
  p.latest_score,
  p.prior_score,
  (p.latest_score - p.prior_score) AS growth,
  CASE
    WHEN p.prior_score IS NULL THEN 'No Data'
    WHEN (p.latest_score - p.prior_score) >= 2 THEN 'Improving'
    WHEN (p.latest_score - p.prior_score) <= -2 THEN 'Declining'
    ELSE 'Stable'
  END AS trend
FROM pairs p;

-- 2.5 v_priority_students: priority_score + reasons + support_status for teacher workflow
DROP VIEW IF EXISTS public.v_priority_students;
CREATE VIEW public.v_priority_students AS
SELECT
  ss.enrollment_id,
  ss.display_name,
  ss.teacher_name,
  ss.school_year,
  ss.grade_level,
  ss.class_name,
  ss.subject_area,
  ss.latest_score,
  ss.support_status,
  ss.tier,
  g.trend,
  ss.days_since_assessment,
  ss.has_active_intervention,
  (
    (CASE WHEN ss.tier = 'Intensive' THEN 5 WHEN ss.tier = 'Strategic' THEN 3 ELSE 0 END) +
    (CASE WHEN g.trend = 'Declining' THEN 3 WHEN g.trend = 'Stable' THEN 1 ELSE 0 END) +
    (CASE WHEN ss.days_since_assessment > 90 THEN 2 WHEN ss.days_since_assessment > 60 THEN 1 ELSE 0 END) +
    (CASE WHEN ss.has_active_intervention = FALSE AND ss.tier IN ('Intensive', 'Strategic') THEN 2 ELSE 0 END)
  )::INT AS priority_score,
  TRIM(BOTH ' |' FROM CONCAT_WS(' | ',
    CASE WHEN ss.tier = 'Intensive' THEN 'Intensive tier' WHEN ss.tier = 'Strategic' THEN 'Strategic tier' END,
    CASE WHEN g.trend = 'Declining' THEN 'Declining growth trend' END,
    CASE WHEN ss.has_active_intervention = FALSE AND ss.tier IN ('Intensive', 'Strategic') THEN 'No active intervention' END,
    CASE WHEN ss.days_since_assessment > 90 THEN 'Overdue assessment (>90d)' END
  )) AS reasons
FROM public.v_support_status ss
LEFT JOIN public.v_growth_last_two g
  ON g.enrollment_id = ss.enrollment_id
 AND g.subject_area = ss.subject_area
 AND g.school_year = ss.school_year;

-- -----------------------------------------------------------------------------
-- 2.6 tier_history: for tier movement KPIs and "Recent changes"
-- Write a row whenever new assessments are entered or on nightly job.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tier_history (
  history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id UUID NOT NULL REFERENCES public.student_enrollments(enrollment_id),
  subject_area TEXT NOT NULL,
  assessment_period TEXT,
  school_year TEXT NOT NULL,
  tier TEXT NOT NULL,
  support_status TEXT NOT NULL,
  latest_score NUMERIC,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(enrollment_id, subject_area, school_year, assessment_period)
);

CREATE INDEX IF NOT EXISTS idx_tier_history_enrollment_subject
ON public.tier_history(enrollment_id, subject_area);

CREATE INDEX IF NOT EXISTS idx_tier_history_computed
ON public.tier_history(computed_at DESC);
