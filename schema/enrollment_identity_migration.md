# Enrollment & Student Identity Migration

This document describes the **decoupled student identity** model: stable person identity vs. grade/year/class context. The database has been migrated to support longitudinal tracking and teacher-based workflows.

---

## Why This Change

**Old model (incorrect):**
- `students` table mixed identity with context: each row had `student_name`, `grade_level`, `class_name`, `teacher_name`, `school_year`.
- Every grade/year change created a new "student" row.
- No stable identity; long-term tracking broke.

**New model:**
- **Identity** lives in `students_core` (one row per person).
- **Context** lives in `student_enrollments` (one row per grade/year/class assignment).
- Assessments link to `enrollment_id` so context is preserved and the system is multi-year scalable.

---

## New Tables

### 1. `students_core` (Stable Identity)

| Column        | Type         | Description                    |
|---------------|--------------|--------------------------------|
| student_uuid  | UUID, PK     | Stable identity for the person |
| display_name  | TEXT         | Name shown in UI              |
| active        | BOOLEAN      | Whether record is active       |
| created_at    | TIMESTAMPTZ  |                                |
| updated_at    | TIMESTAMPTZ  |                                |

- **One row per real student.** Never changes when grade or year changes.

### 2. `student_enrollments` (Context)

| Column        | Type         | Description                          |
|---------------|--------------|--------------------------------------|
| enrollment_id | UUID, PK     | Unique enrollment record             |
| student_uuid  | UUID, FK     | → students_core.student_uuid         |
| school_year   | TEXT         | e.g. 2024-25                        |
| grade_level   | TEXT         | e.g. K, 1, 2                        |
| class_name    | TEXT         | e.g. K-B                             |
| teacher_name  | TEXT         |                                      |
| created_at    | TIMESTAMPTZ  |                                      |
| updated_at    | TIMESTAMPTZ  |                                      |

- **One row per grade/year/class assignment.** A student can have many enrollments over time.
- Optional: `legacy_student_id` (INT, FK → students.student_id) for bridge to legacy scores/interventions.

### 3. `student_id_map` (Migration Bridge)

| Column            | Type    | Description                    |
|-------------------|---------|--------------------------------|
| legacy_student_id| INTEGER | Old students.student_id        |
| student_uuid      | UUID    | → students_core.student_uuid   |

- Maps legacy IDs to stable UUIDs so existing FKs and score tables keep working during phased migration.

---

## Updated Tables

### `assessments`

- **Added:** `enrollment_id` (UUID, FK → student_enrollments.enrollment_id).
- Backfilled so every assessment links to the correct enrollment.
- **Kept:** `student_id` for phased migration (not removed yet).

---

## What Stays the Same (For Now)

- **`students`** table: not deleted; kept for backward compatibility.
- **`student_id`** on assessments: not removed.
- **`literacy_scores` / `math_scores`**: still keyed by `student_id` (legacy). Joined to enrollments via `legacy_student_id` or `student_id_map`.
- **`interventions`**: still keyed by `student_id`. Resolved from enrollment via legacy_student_id.
- Teachers and classes are not yet normalized into separate tables.

---

## Data Flow

```
students_core (person)
        ↓
student_enrollments (grade/year/class context)
        ↓
assessments (enrollment_id)
interventions (student_id via legacy bridge)
teacher_notes
student_goals
```

---

## UI / API Contract

- **List view (dashboard):** Query `student_enrollments` joined to `students_core`. Display: `display_name` + “Grade • Year • Teacher • Class”. Store and use `enrollment_id` as the primary key for navigation.
- **Detail view:** Load by **enrollment_id**: `/app/:subject/enrollment/:enrollment_id`. Fetch enrollment + assessments (by enrollment_id) + interventions (by legacy_student_id for that enrollment).
- **Dropdowns:** Options are enrollments (value = `enrollment_id`), label = e.g. “Ada • Kindergarten • 2024–25 • Mrs. Garcia • K-B”.

---

## Resolving Legacy IDs

- For a given `enrollment_id`, get `student_uuid` from `student_enrollments`.
- If `student_enrollments.legacy_student_id` exists, use it for literacy_scores / math_scores / interventions.
- Otherwise resolve one `legacy_student_id` from `student_id_map` where `student_uuid` = enrollment’s `student_uuid` (e.g. `LIMIT 1` if multiple).

---

## Canonical bootstrap

For the full schema setup order (base schema → this identity model → dashboard views), see **[docs/SCHEMA_BOOTSTRAP.md](../docs/SCHEMA_BOOTSTRAP.md)**.
