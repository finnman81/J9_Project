# Student Detail API – Trace / Troubleshooting

This file is a short **trace and troubleshooting** supplement. For the full description of how data is retrieved and displayed, see **[STUDENT_DETAIL_DATA_AND_API.md](./STUDENT_DETAIL_DATA_AND_API.md)**.

## Quick reference

- **Endpoint:** `GET /api/student-detail/{student_uuid}?subject=Math` (optional: `enrollment_ids=id1,id2`)
- **Backend:** `api/routers/students.py` → `get_student_detail_by_uuid()`
- **Frontend:** `web/src/pages/StudentDetail.tsx` (fetch on UUID/enrollment change; `displayHeader` fills KPIs from assessments when API header has nulls)
- **DB views:** `v_support_status`, `v_growth_last_two` (`schema/migration_v3_teacher_first.sql`)

## Common issues

| Symptom | Cause | See |
|--------|--------|-----|
| KPIs blank but assessments table has data | API header nulls and frontend fallback not running, or wrong response shape | STUDENT_DETAIL_DATA_AND_API.md § 4.3 |
| Reading interventions on Math page | Interventions not filtered by subject | Backend now filters by `subject_area`; see § 3.2 in main doc. |
| Wrong student or no data | URL missing UUID (`/app/math/student` = legacy mode) or wrong `subject` param | § 2 and § 3.1 in main doc. |

## Data flow (one sentence)

Frontend calls student-detail API with UUID and subject → backend loads enrollments, then assessments/interventions/notes/goals/support (subject-filtered where applicable) and builds header from assessments first → frontend stores response and derives any missing KPI fields from assessments/interventions so the summary cards stay populated.
