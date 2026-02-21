-- =============================================================================
-- Migration V4: Performance indexes for dashboard metrics endpoints
-- Run after migration_v3. Safe to run idempotently.
-- Targets: teacher-kpis, priority-students, distribution, growth (v_support_status,
-- v_priority_students, v_growth_last_two filtered by teacher_name, school_year,
-- grade_level, class_name on student_enrollments).
-- =============================================================================

-- Dashboard filter columns on student_enrollments (v_teacher_roster base)
-- migration_v3 already has idx_enrollments_teacher_year(teacher_name, school_year)
CREATE INDEX IF NOT EXISTS idx_enrollments_grade_level
ON public.student_enrollments(grade_level);

CREATE INDEX IF NOT EXISTS idx_enrollments_class_name
ON public.student_enrollments(class_name);

-- Composite for common filter combination (teacher + year + grade/class)
CREATE INDEX IF NOT EXISTS idx_enrollments_dashboard_filters
ON public.student_enrollments(teacher_name, school_year, grade_level, class_name);

-- benchmark_thresholds used by distribution and v_support_status join
CREATE INDEX IF NOT EXISTS idx_benchmark_thresholds_subject_year
ON public.benchmark_thresholds(subject_area, school_year);
