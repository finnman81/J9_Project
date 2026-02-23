# Hosting Recommendations (2026) for This SaaS App (AWS-leaning)

## Scope
This document maps deployment options to the **current stack in this repo**:
- React + Vite frontend (`web/`)
- FastAPI backend (`api/`)
- PostgreSQL data layer (currently Supabase/Postgres)
- Legacy Streamlit app still present

## Current stack and readiness snapshot

### What is already production-friendly
- Clear split between frontend and API services.
- API has health endpoint and structured error handling (`/health`, JSON error shape).
- CORS is environment-driven via `CORS_ORIGINS`.
- Frontend can target a remote API through `VITE_API_URL`.
- Database is externalized via `DATABASE_URL`.

### Gaps before public SaaS launch
- No containerization yet (no Dockerfile).
- No CI/CD workflows in repo.
- No authentication/authorization enforcement in API routes.
- No managed secrets strategy documented for hosted environments.
- No production observability (metrics/tracing/alerts) setup.

## Recommended hosting path (best balance of easy + scalable in 2026)

### Recommendation: **AWS App Runner + AWS Amplify Hosting + Supabase (Phase 1)**
This is the easiest path to a stable public launch while minimizing migration risk.

1. **Frontend**: deploy `web/` on **AWS Amplify Hosting** (or CloudFront/S3 if you prefer manual infra).
2. **API**: package FastAPI in a container and deploy to **AWS App Runner**.
3. **Database**: keep current Supabase Postgres initially (least risky), then optionally migrate to AWS Postgres later.
4. **Secrets**: use **AWS Secrets Manager** (or SSM Parameter Store) for `DATABASE_URL`, CORS, and app env vars.
5. **Observability**: CloudWatch logs/alarms + X-Ray/OpenTelemetry for API traces.

Why this is best for this repo in 2026:
- Minimal platform work for team size typical of early SaaS.
- Keeps frontend/backend split already present.
- Lets you ship quickly without immediate database migration complexity.
- Can evolve to ECS/Fargate or EKS later without rewriting app logic.

## Alternative paths

### Option A (fastest launch): Full Supabase + Vercel/Netlify frontend + App Runner API
- Fastest to ship, but less AWS-centric.

### Option B (AWS-pure target state): Amplify + ECS/Fargate + RDS Postgres + ElastiCache
- Most control and enterprise alignment; higher operational overhead.

### Option C (single-service compromise): Amplify + Lambda/API Gateway + Aurora Serverless v2
- Works if API pattern becomes highly request-spiky and stateless.
- Requires more adaptation for data-heavy pandas-like operations.

## Target reference architecture (recommended)

### Edge + web
- Route53 (domain)
- AWS WAF + Shield Standard
- Amplify Hosting (React static build) or CloudFront+S3

### API
- App Runner service for FastAPI container
- `/health` used for health checks
- Autoscaling by concurrent requests

### Data
- Phase 1: Supabase Postgres
- Phase 2: RDS Postgres or Aurora Postgres (if compliance/cost/perf requires)

### Security and identity
- Add Cognito (or Auth0/Clerk) before full multi-tenant rollout
- Enforce JWT validation in FastAPI middleware/dependencies
- Role model: `admin`, `teacher`, `specialist` (and tenant/school scoping)

### Ops
- Secrets Manager for env vars
- CloudWatch dashboards/alarms
- Error tracking (Sentry) + basic SLOs

## Practical rollout plan

### Phase 0 — hardening (1-2 sprints)
- Add Dockerfile for API and standard startup command (`uvicorn api.main:app --host 0.0.0.0 --port 8080`).
- Add request timeouts and gunicorn/uvicorn worker tuning for production.
- Lock CORS to actual domains only.
- Introduce auth guardrails for protected routes.

### Phase 1 — first public deployment
- Deploy frontend to Amplify with `VITE_API_URL` pointing to App Runner URL.
- Deploy API container to App Runner.
- Store runtime secrets in Secrets Manager.
- Configure HTTPS custom domains for frontend and API.

### Phase 2 — production operations
- Add CI/CD (GitHub Actions): test -> build -> deploy.
- Add DB migration pipeline (idempotent schema migration scripts).
- Add CloudWatch alarms: 5xx rate, latency p95, CPU/memory.

### Phase 3 — scale and enterprise readiness
- Add multi-tenant row-level security strategy (app or DB level).
- Consider RDS/Aurora migration when needed.
- Add background jobs (SQS + worker service) for heavy data tasks/imports.

## Estimated effort vs benefit
- **Best near-term ROI**: App Runner + Amplify + keep Supabase for now.
- **Highest long-term control**: ECS/Fargate + RDS.
- **Do not overbuild early**: skip Kubernetes until clear scale/team need.

## 2026 opinionated recommendation (final)
If your priority is to launch quickly and still stay AWS-leaning:
1. Launch web on **Amplify Hosting**.
2. Launch FastAPI on **App Runner**.
3. Keep Supabase Postgres for first release.
4. Add Cognito + JWT auth before onboarding real schools.
5. Re-evaluate DB migration to RDS/Aurora after usage patterns stabilize.

This gives the best balance of speed, reliability, and migration safety for your current codebase.
