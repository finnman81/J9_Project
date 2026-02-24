# Hosting Recommendations (2026) — Multi-School SaaS on AWS

## Scope
This document maps deployment options to the **current stack in this repo**:
- React + Vite + Tailwind frontend (`web/`)
- FastAPI backend (`api/`)
- PostgreSQL data layer (currently Supabase/Postgres)

The target is a **production-ready, multi-tenant SaaS** that can onboard and scale across multiple schools independently.

## Current stack and readiness snapshot

### What is already production-friendly
- Clear split between frontend and API services.
- API has health endpoint and structured error handling (`/health`, JSON error shape).
- CORS is environment-driven via `CORS_ORIGINS`.
- Frontend can target a remote API through `VITE_API_URL`.
- Database is externalized via `DATABASE_URL`.
- Enrollment-based data model (`students_core` + `student_enrollments`) already supports per-school scoping.

### Gaps before multi-school SaaS launch
- No containerization yet (no Dockerfile / `.dockerignore`).
- No CI/CD deployment workflows.
- No authentication/authorization enforcement in API routes.
- No tenant isolation strategy (row-level security or schema-per-tenant).
- No managed secrets strategy documented for hosted environments.
- No production observability (metrics/tracing/alerts) setup.
- No staging/preview environment strategy.

## Recommended hosting path

### Recommendation: **AWS App Runner + AWS Amplify Hosting + Supabase (Phase 1)**
Best balance of speed-to-launch, operational simplicity, and room to scale across schools.

1. **Frontend**: deploy `web/` on **AWS Amplify Hosting** (auto-builds from repo, branch previews for staging).
2. **API**: package FastAPI in a container and deploy to **AWS App Runner** (auto-scaling, managed TLS, zero cluster ops).
3. **Database**: keep current Supabase Postgres initially (least risky), then migrate to AWS-managed Postgres when multi-tenant compliance or performance requires it.
4. **Secrets**: use **AWS Secrets Manager** (or SSM Parameter Store) for `DATABASE_URL`, CORS origins, auth keys, and per-environment config.
5. **Auth**: add **Clerk** or **Auth0** for identity (better multi-tenant DX than Cognito for role-based school scoping).
6. **Observability**: CloudWatch logs/alarms + Sentry for error tracking + OpenTelemetry for API traces.

Why this is best for this project in 2026:
- Minimal platform work for a small team.
- Preserves the frontend/backend split already in place.
- Ships quickly without immediate database migration.
- Evolves to ECS/Fargate or EKS later without rewriting app logic.
- Amplify branch previews give you staging for free.

## Alternative paths

### Option A (fastest launch): Full Supabase + Vercel/Netlify frontend + App Runner API
- Fastest to ship, but less AWS-centric and harder to consolidate billing/networking later.

### Option B (AWS-pure target state): Amplify + ECS/Fargate + RDS Postgres + ElastiCache
- Most control and enterprise alignment; higher operational overhead. Best suited once you have dedicated DevOps capacity.

### Option C (serverless): Amplify + Lambda/API Gateway + Aurora Serverless v2
- **Not recommended for this project.** The API has data-heavy routers (metrics, dashboard, assessments) that involve aggregation queries and pandas operations. Lambda cold starts and execution limits create friction here. Only revisit if the workload becomes highly request-spiky and stateless.

## Target reference architecture

### Edge + web
- Route53 (custom domain)
- AWS WAF + Shield Standard
- Amplify Hosting (React static build, branch previews for staging/QA)

### API
- App Runner service for FastAPI container
- `/health` used for health checks
- Autoscaling by concurrent requests
- Separate App Runner services for staging vs production

### Data
- Phase 1: Supabase Postgres (current)
- Phase 2: RDS Postgres or Aurora Postgres (when compliance, performance, or tenant isolation requires AWS-managed DB)

### Multi-tenancy and identity
- Auth provider: **Clerk** or **Auth0** (better multi-tenant support than Cognito)
- JWT validation enforced in FastAPI middleware/dependencies
- Role model: `admin`, `teacher`, `specialist` with school/tenant scoping
- Tenant isolation strategy (choose one based on scale):
  - **Row-level security (RLS)** with `school_id` on every tenant table — simplest, works well up to ~50-100 schools
  - **Schema-per-tenant** — stronger isolation, more migration complexity
  - **Database-per-tenant** — strongest isolation, highest operational overhead (only if regulatory requirements demand it)
- Recommended starting point: **RLS with `school_id`** column, enforced at the Postgres level and validated in API middleware

### Ops
- Secrets Manager for env vars (per environment)
- CloudWatch dashboards/alarms (5xx rate, p95 latency, CPU/memory)
- Sentry for error tracking
- Basic SLOs defined before onboarding schools

## Practical rollout plan

### Phase 0 — hardening (1-2 sprints)
- Add `Dockerfile` and `.dockerignore` for API service (`uvicorn api.main:app --host 0.0.0.0 --port 8080`).
- Add request timeouts and uvicorn worker tuning for production.
- Lock CORS to actual domains only.
- Add basic CI/CD pipeline (GitHub Actions): lint, test, build container, push to ECR.
- Define environment strategy: `staging` (Amplify branch preview + separate App Runner service) and `production`.

### Phase 1 — first public deployment
- Deploy frontend to Amplify with `VITE_API_URL` pointing to App Runner URL.
- Deploy API container to App Runner via CI/CD pipeline.
- Store runtime secrets in Secrets Manager.
- Configure HTTPS custom domains for frontend and API.
- Add auth provider (Clerk/Auth0) and enforce JWT validation on all protected API routes.
- Set up Sentry error tracking.

### Phase 2 — multi-school readiness
- Add `school_id` tenant column to core tables and enforce RLS in Postgres.
- Add tenant-aware API middleware (extract school context from JWT claims).
- Add school onboarding workflow (create school record, invite admin user, seed config).
- Add DB migration pipeline (idempotent schema migration scripts).
- Add CloudWatch alarms: 5xx rate, latency p95, CPU/memory.
- Define and publish SLOs for uptime and response time.

### Phase 3 — UI/UX polish
- Typography refinement: tighten line heights, establish clear font weight hierarchy, consistent sizing scale across all pages.
- Spacing and density pass: audit padding/margins for consistency, optimize content density on data-heavy screens (dashboards, student detail).
- Micro-interactions: smooth hover/focus transitions, skeleton loading states instead of spinners, subtle page transition animations.
- Data visualization polish: custom Recharts color palettes per theme, refined tooltips, responsive chart sizing.
- Empty states and edge cases: design proper zero-data states (no students, no assessments, first-time setup), error states, and loading feedback.
- Per-school branding refinement: ensure theme system covers all visual touchpoints (charts, badges, risk colors, print styles).

### Phase 4 — scale and enterprise readiness
- Consider RDS/Aurora migration when Supabase limits are reached or compliance requires it.
- Add background jobs (SQS + worker service) for heavy data tasks/imports/bulk operations.
- Add per-school usage metering if moving to paid tiers.
- Evaluate ECS/Fargate if App Runner scaling limits are hit.
- Add audit logging for compliance (who accessed what data, when).

## Estimated effort vs benefit
- **Best near-term ROI**: App Runner + Amplify + keep Supabase + Clerk/Auth0.
- **Highest long-term control**: ECS/Fargate + RDS + custom auth.
- **Do not overbuild early**: skip Kubernetes until clear scale/team need.

## Estimated monthly cost (low-traffic early SaaS)
- App Runner (1 instance, auto-pause): ~$15-25/mo
- Amplify Hosting: ~$0-5/mo (free tier covers most early usage)
- Supabase (Pro plan): ~$25/mo
- Secrets Manager: ~$1-2/mo
- Sentry (free tier): $0
- Auth provider (Clerk/Auth0 free tier): $0
- **Total estimate: ~$40-60/month** scaling up with usage

## Final recommendation
If your priority is to launch a production-ready, multi-school SaaS while staying AWS-leaning:

1. Launch web on **Amplify Hosting** (with branch previews for staging).
2. Launch FastAPI on **App Runner** (with CI/CD from day one).
3. Keep Supabase Postgres for first release.
4. Add **Clerk or Auth0** with JWT auth before onboarding any schools.
5. Implement **row-level security with `school_id`** for tenant isolation.
6. Re-evaluate DB migration to RDS/Aurora after usage patterns stabilize across schools.

This gives the best balance of speed, reliability, multi-tenant safety, and migration flexibility for the current codebase.
