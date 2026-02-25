# Deployment Branch Review (2026-02-24)

## Scope
Reviewed cloud-deployment readiness for FastAPI (`api/`) + Vite React (`web/`) with focus on runtime behavior, config correctness, and operational readiness.

## Executive summary
- **Status:** Branch is close to deployable, but has several documentation and reliability gaps.
- **Most important fix:** Make container runtime bind to injected `PORT` for broader cloud compatibility.
- **Main risk areas:** outdated deployment docs, weak CI quality gates, and inconsistent project guidance.

## Findings

### High
1. **Container ignored platform-provided port (fixed in this branch).**
   - Before this fix, Gunicorn always bound to `0.0.0.0:8080` even if a platform injects a different `PORT`.
   - This can break startups on platforms where the runtime contract requires binding to `$PORT`.

### Medium
2. **Deployment documentation is inconsistent with current architecture.**
   - `docs/DEPLOY.md` still describes Streamlit Community Cloud + `app.py` as primary deployment path.
   - Current app stack in repo is React (`web/`) + FastAPI (`api/`) with auth and API routing.

3. **Hosting recommendations contain stale statements.**
   - `docs/HOSTING_RECOMMENDATIONS_2026.md` says there is no containerization and no auth enforcement, but repo now includes a Dockerfile and JWT auth dependencies in API routing.

4. **Test coverage is effectively absent in CI signal.**
   - Current test run is fully skipped (`13 skipped`), so regressions in deployment behavior are unlikely to be caught automatically.

### Low
5. **Code quality/lint debt is high (not deployment-blocking, but impacts maintainability).**
   - `ruff check api core` reports a large set of import-order, unused import, and whitespace issues.

## Recommendations
1. Update deployment docs to clearly separate:
   - **Legacy Streamlit path**
   - **Current FastAPI + React production path**
2. Add a basic CI workflow that fails on:
   - backend lint
   - frontend lint/build
   - at least one non-skipped backend smoke test
3. Add staging/prod config matrix doc (required env vars, expected URLs, CORS values, auth issuer values).
4. Add one deploy smoke check script (`/health`, JWT-protected endpoint, DB connectivity).

## Checks run
- `pytest -q` (13 skipped)
- `python -m compileall api core`
- `npm --prefix web run build`
- `npm --prefix web run lint`
- `ruff check api core` (fails with existing lint debt)
