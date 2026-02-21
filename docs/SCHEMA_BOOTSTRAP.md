# Canonical Schema Bootstrap (Migration-First)

This document describes the **recommended** way to set up the database schema. Use this path for new deployments and for existing databases that need the full enrollment-based model and dashboard views.

## Order of operations

1. **Base schema**  
   Run `schema/supabase_schema.sql` (and optionally `schema/supabase_schema_math.sql` for math-specific tables) in your PostgreSQL/Supabase SQL Editor. This creates the legacy `students`, `assessments`, `interventions`, `literacy_scores`, `math_scores`, etc.

2. **Enrollment identity**  
   Create `students_core`, `student_enrollments`, `student_id_map`, and add `enrollment_id` to `assessments` (and backfill). See [schema/enrollment_identity_migration.md](../schema/enrollment_identity_migration.md) for the model and data flow.

3. **Dashboard views (V3)**  
   Run migration V3 to add views and indexes required by the dashboard and API:
   ```bash
   python run_migration_v3.py
   ```
   Or execute `schema/migration_v3_teacher_first.sql` in the SQL Editor. This creates `v_teacher_roster`, `v_support_status`, `v_priority_students`, `v_growth_last_two`, and related indexes.

4. **Performance indexes (V4)**  
   Optional but recommended for dashboard performance.  
   Run the performance index migration for dashboard filter columns:
   ```bash
   # From project root, using psql or your SQL Editor:
   psql "$DATABASE_URL" -f schema/migration_v4_perf_indexes.sql
   ```
   Or execute `schema/migration_v4_perf_indexes.sql` in the SQL Editor.

## Legacy fallback: `init_database()`

The function `core.database.init_database()` only creates the **legacy** tables (`students`, `assessments`, `interventions`, etc.). It does **not** create `students_core`, `student_enrollments`, or the V3 views. Use it only for local or legacy setups that do not use the migration SQL files. For the full app (dashboard, enrollment-based student detail), use the migration-first path above.

## Verification

- After V3, the API and Overview Dashboard should work if `student_enrollments` has data.
- Check that views exist: `v_support_status`, `v_priority_students`, `v_growth_last_two` (e.g. in Supabase Table Editor or `\dv` in psql).
