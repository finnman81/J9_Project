# Full Codebase Review (Frontend + Backend + Database)

Date: 2026-02-20
Reviewer: Codex

## Executive summary

The project has good momentum and clear product direction, and this PR now includes both:

1. **A full-stack audit** of stale/redundant code, risks, and architectural drift.
2. **Implemented performance + reliability upgrades** to reduce unnecessary renders/fetch churn and clean up test/lint gates.

## Audit findings

### 1) Frontend: hook dependency and memoization issues were causing avoidable work

- Dashboard/analytics pages had effect dependency and memo patterns that could trigger stale computations or repeated work.
- Some pages also had unused variables/imports and fallback logic that made behavior harder to reason about.

### 2) Testing: pytest collection was broken by helper naming

- A utility function in `test_api_endpoints.py` was named with a `test_` prefix, so pytest attempted to collect it as a test and failed fixture resolution.

### 3) Database model drift risk remains

- Enrollment identity migration docs describe `students_core` + `student_enrollments`, while legacy bootstrap/schema paths still exist.

### 4) Backend hardening opportunities remain

- CORS and broad exception fallback behavior should still be tightened in a follow-up backend-focused PR.

### 5) Repository hygiene follow-up remains

- `node_modules` cleanup and ignore rules should be handled in a dedicated repo-hygiene PR.

## Implemented upgrades in this PR

### Frontend performance/reliability

- Refactored data-loading effects in Overview/Analytics/Teacher dashboard pages to use cancellable async flows and avoid stale-response state updates after unmount or fast filter changes.
- Tightened effect dependencies to stable memo objects where appropriate.
- Removed noisy dashboard debug logging in data-fetch paths.
- Fixed memo dependencies in dashboard list/chart derivations.
- In student detail, memoized assessment-type derivation and fixed latest-score derivation logic to correctly use newest scored row.

### Quality gates / correctness

- Resolved frontend lint blockers (including unused vars/imports and hook dependency issues).
- Fixed pytest collection by renaming the helper function in `test_api_endpoints.py` from `test_*` naming to a non-test helper name.
- Corrected metrics script calls to use `subject=` for priority endpoint parity.

## Expected impact on loading speed

These implemented changes should improve perceived and real loading behavior by:

- Reducing repeated render/fetch churn during filter changes.
- Preventing outdated async responses from overwriting newer state.
- Improving derivation efficiency for student detail filters.

The largest gains are on overview and analytics pages where multiple endpoints load concurrently.

## Recommended next steps (separate PRs)

1. Add request cancellation support in shared API client via `AbortController` signals.
2. Add backend query profiling + indexes for top dashboard endpoints.
3. Tighten API CORS and replace broad catch/fallback branches with explicit error handling.
4. Finalize canonical schema bootstrap path (migration-first vs helper init code).
5. Remove tracked `node_modules` and add ignore rule to prevent recurrence.
