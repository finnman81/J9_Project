# Student Detail: Data Retrieval & Frontend Display

This document describes how the **Student Detail** page (Math and Reading) retrieves data from the API and how the frontend displays it.

---

## 1. Overview

The Student Detail page shows a single student’s assessments, interventions, notes, and goals for either **Math** or **Reading**. Data is loaded in one API call per student/subject; the frontend then derives summary KPIs from that response so the top cards are never blank when assessment data exists.

---

## 2. URL and routing

| URL pattern | Mode | Description |
|-------------|------|-------------|
| `/app/:subject/student/:studentUuid` | UUID | Student detail by `students_core.student_uuid`. Data from `GET /api/student-detail/{uuid}?subject=...`. |
| `/app/:subject/student` | UUID | Same flow: enrollment-based student picker; selecting a student navigates to `.../student/:uuid` and loads via student-detail API. |
| `/app/:subject/enrollment/:enrollmentId` | Enrollment | Redirects to UUID mode using the enrollment’s `student_uuid`. |

For the main flow below, **subject** = `math` or `reading`, **studentUuid** = UUID from the route.

---

## 3. API: how data is retrieved

### 3.1 Endpoint

- **Method/URL:** `GET /api/student-detail/{student_uuid}?subject=Math`
- **Optional:** `enrollment_ids=id1,id2,...` to restrict to specific enrollments.
- **Handler:** `api/routers/students.py` → `get_student_detail_by_uuid()`

### 3.2 Backend flow

1. **Enrollments**  
   Load all enrollments for the student: `get_enrollments_for_student_uuid(student_uuid)`.  
   If `enrollment_ids` is provided, filter to those IDs; otherwise use **all** enrollments for the student.

2. **Subject**  
   `subject_area = "Reading"` if `subject.lower() == "reading"`, else `"Math"`.  
   All subject-specific data uses this value.

3. **Data loaded (in order)**

   | Data | Function | Subject filtering |
   |------|----------|-------------------|
   | Assessments | `get_multi_enrollment_assessments(selected, subject_area=subject_area)` | Yes – only requested subject. |
   | Interventions | `get_multi_enrollment_interventions(selected)` then filtered in Python | Yes – keep only rows where `subject_area == subject_area` (Math page shows only Math interventions). |
   | Notes | `get_multi_enrollment_notes(selected)` | No. |
   | Goals | `get_multi_enrollment_goals(selected)` | No. |
   | Support (tier, trend, etc.) | `get_multi_enrollment_support_status(selected, subject_area)` | Yes – one row from `v_support_status` for that subject. |
   | Growth | `get_multi_enrollment_growth(selected, subject_area)` | Yes. |

4. **Header KPIs (backend)**  
   The API builds a `header` object for the summary cards:

   - **Latest score & last assessed date**  
     Derived first from the **assessments** returned for this request: sort by `effective_date` / `assessment_date`, take the latest row with a normalized score; use its `score_normalized` and date.  
     If the support view has data, it can overlay tier/trend and (optionally) score/date.

   - **Tier / risk, trend**  
     From `v_support_status` and `v_growth_last_two` when available.

   - **Intervention**  
     From support view’s `has_active_intervention`, with fallback: if the (subject-filtered) interventions list has any active status, set `has_active_intervention: true`.

   - **Goal status**  
     `"Has goals"` if the goals list is non-empty, else `"No goals"`.

   All header values are passed through `serialize_dict()` so they are JSON-serializable (no numpy/Decimal in the response).

5. **Response shape**  
   The endpoint returns a single JSON object, e.g.:

   ```json
   {
     "student_uuid": "...",
     "display_name": "Andrea",
     "enrollments": [ { "enrollment_id", "school_year", "grade_level", ... } ],
     "selected_enrollment_ids": [ "..." ],
     "header": {
       "latest_score": 64,
       "tier": "Core",
       "trend": "Stable",
       "last_assessed_date": "2026-02-12",
       "days_since_assessment": 4,
       "has_active_intervention": false,
       "goal_status": "No goals"
     },
     "score_over_time": [ { "period": "Fall 2024-25", "score": 64 }, ... ],
     "assessments": [ { "assessment_type", "assessment_period", "score_normalized", "effective_date", "assessment_date", ... } ],
     "interventions": [ ... ],
     "notes": [ ... ],
     "goals": [ ... ]
   }
   ```

---

## 4. Frontend: how data is displayed

### 4.1 Fetching

- **File:** `web/src/pages/StudentDetail.tsx`
- **When:** In UUID mode, when `studentUuidParam` (and optionally enrollment filter) changes.
- **Call:** `api.getStudentDetailByUuid(studentUuidParam, subjectLabel, enrollmentIds)`  
  - `subjectLabel` = `"Math"` or `"Reading"` from the route (`subject`).
  - If no enrollment filter, `enrollmentIds` is `undefined` (backend uses all enrollments).

- **Client:** `web/src/api/client.ts`  
  - Builds: `GET /api/student-detail/{studentUuid}?subject=Math` (and optional `enrollment_ids=...`).
  - Uses `request<T>()` (fetch + JSON); base URL from `VITE_API_URL` or relative (Vite proxy to API).

### 4.2 State set from response

The response is stored and used for both the KPI strip and the tables:

- `setUuidDetail(d)` – full response (includes `header`, `enrollments`, `assessments`, etc.).
- `setHeader(d.header)`.
- `setAssessments(d.assessments)`.
- `setInterventions(d.interventions)`.
- `setScoresHistory(d.score_over_time)`.
- `setNotes(d.notes)`.
- `setGoals(d.goals)`.

So the **Assessments** and **Interventions** tables render directly from `d.assessments` and `d.interventions` (already subject-filtered by the API).

### 4.3 Display header (KPIs) and fallbacks

The top summary cards use a computed **displayHeader** so that KPIs are never blank when the page has assessment data:

- **Legacy mode** (URL without UUID, legacy student picker):  
  If there is `scoresHistory`, display header is built from that plus interventions/goals (e.g. latest score from last history point).

- **UUID mode** (normal Student Detail by UUID):
  - Base: `uuidDetail.header` (or `header` state) from the API.
  - **When the API header is missing or has nulls:**  
    The frontend derives:
    - **Latest score** from the **assessments** list: among rows with `score_normalized`, take the one with the latest `effective_date` / `assessment_date` and use its `score_normalized`.
    - **Last assessed** from that same assessment’s date.
    - **Intervention** from the current `interventions` list (any status containing “active” / “progress” / “ongoing”).
    - **Goal status** from whether `goals.length > 0`.
  - So even if the API returns nulls for some header fields, the cards show values as long as the assessments (and interventions/goals) are present in the response.

### 4.4 What appears where

| UI element | Data source | Notes |
|------------|-------------|--------|
| Page title | Route `subject` | “Math Student Detail” / “Reading Student Detail”. |
| Student dropdown | `uuidDetail.enrollments` / `allEnrollments` | In UUID mode, options from enrollments’ student UUIDs/names. |
| Enrollment filter chips | `uuidDetail.enrollments` | Optional filter; re-fetches with `enrollment_ids` when changed. |
| **Latest Score** | `displayHeader.latest_score` | From API header or derived from latest assessment with score. |
| **Tier / Risk** | `displayHeader.tier` | From API (support view); may be “—” if unknown. |
| **Trend** | `displayHeader.trend` | From API (growth view). |
| **Last assessed** | `displayHeader.last_assessed_date` | From API or derived from latest assessment date. |
| **Intervention** | `displayHeader.has_active_intervention` | “Active” or “None”; from API or derived from interventions list. |
| **Goal status** | `displayHeader.goal_status` | From API or from whether goals list is non-empty. |
| **Assessments table** | `assessments` (from response) | Columns: Type, Period, Score, Date. Date shows `assessment_date ?? effective_date`. |
| **Interventions table** | `interventions` (from response) | Subject-filtered on backend (Math page = only Math interventions). |
| **Score over time chart** | `score_over_time` (from response) | Built on backend from assessments. |
| Notes / Goals | `notes`, `goals` (from response) | Rendered as-is. |

---

## 5. Database and views (reference)

- **Enrollments:** `student_enrollments` (joined with `students_core` for display name).
- **Assessments:** `assessments`; filtered by `enrollment_id` and `subject_area`; ordered by date/period.
- **Interventions:** `interventions`; filtered by `enrollment_id` and then by `subject_area` in the student-detail endpoint.
- **Support status (tier, latest score from view):** `v_support_status` (from `v_teacher_roster` + benchmark thresholds) in `schema/migration_v3_teacher_first.sql`.
- **Growth/trend:** `v_growth_last_two` in the same migration.

---

## 6. Key code references

| Layer | File | Notes |
|-------|------|--------|
| API route | `api/routers/students.py` | `get_student_detail_by_uuid` (student-detail by UUID). |
| DB helpers | `core/database.py` | `get_enrollments_for_student_uuid`, `get_multi_enrollment_assessments`, `get_multi_enrollment_interventions`, `get_multi_enrollment_support_status`, `get_multi_enrollment_growth`, etc. |
| Serialization | `api/serializers.py` | `serialize_dict`, `dataframe_to_records` (JSON-safe responses). |
| Frontend page | `web/src/pages/StudentDetail.tsx` | Fetch, state, `displayHeader` logic, KPI cards, tables. |
| API client | `web/src/api/client.ts` | `getStudentDetailByUuid`, `request`, types for response. |
| Views | `schema/migration_v3_teacher_first.sql` | `v_teacher_roster`, `v_support_status`, `v_growth_last_two`. |

See **§7 Troubleshooting** for the past issue where tier/trend/notes/goals did not show because the page used legacy mode when the URL had no `studentUuid`.

---

## 7. Troubleshooting: Tier / Trend / Notes / Goals not showing

**Issue (fixed):** If users navigated to Student Detail via the sidebar (e.g. Math → Student Detail), the URL was `/app/math/student` with **no** `studentUuid` in the path. The frontend treated that as **legacy mode** (`isUuidMode = Boolean(studentUuidParam)` was false), so it used the old flow: `getStudents()` and, after picking a student, `getStudent(id)`, `getStudentMathScore(id)`, etc. That path **never** calls `GET /api/student-detail/{uuid}?subject=Math`, so **tier, trend, notes, and goals were never loaded** (and the legacy flow explicitly set notes/goals to empty).

**Fix:** In `web/src/pages/StudentDetail.tsx`, the page now treats **any** URL path that contains `/student` as UUID mode (`isUuidMode = location.pathname.includes('/student')`). So both `/app/math/student` and `/app/math/student/:uuid` use the enrollment-based picker and, when a student is selected, load data via `getStudentDetailByUuid` (student-detail API). Tier, trend, notes, and goals then come from the API response.

**If it resurfaces:** Check that the Student Detail page is not falling back to legacy mode (legacy uses `getStudents()` and numeric `student_id`; UUID mode uses `getEnrollments()` and `student_uuid`). Ensure `isUuidMode` is true whenever the user is on a route whose path includes `/student`.

---

## 8. Summary

- **One request** loads all Student Detail data: `GET /api/student-detail/{uuid}?subject=Math` (optional `enrollment_ids`).
- **Backend** uses subject to filter assessments and interventions, and builds the **header** from assessments first (so latest score and date are set), then support/growth for tier and trend.
- **Frontend** stores the response and uses it for tables and charts; it **fills in missing header fields** from the same assessments and interventions so the KPI strip is never blank when data exists.
- **Interventions** on the Math page are only Math (and similarly for Reading); legacy null-subject interventions are not shown on subject-specific pages.
