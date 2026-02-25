# Deployment configuration matrix

Reference for env vars, URLs, CORS, and auth when deploying the FastAPI + React stack. See [DEPLOY.md](DEPLOY.md) for build/run steps.

---

## Required environment variables

### API (backend)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (e.g. Supabase or RDS). |
| `CORS_ORIGINS` | Yes in production | Comma-separated list of allowed frontend origins. No spaces. |
| `CLERK_JWT_ISSUER` | Yes in production | Clerk JWT issuer URL, no trailing slash (e.g. `https://your-instance.clerk.accounts.dev`). |
| `APP_ENV` | Optional | Set to `production` or `prod` to enforce CORS and auth; otherwise defaults to development. |
| `PORT` | Optional | Port the server binds to (default 8080). Many platforms inject this. |

### Frontend (build-time)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes for remote API | Base URL of the API with no trailing slash (e.g. `https://api.example.com`). For local dev use `http://localhost:8000` or leave unset if your Vite config has a default. |

---

## Expected URLs by environment

Fill in your actual URLs and keep this table updated so deployers know what to set.

| Environment | API base URL | Frontend origin |
|-------------|--------------|-----------------|
| **Staging** | e.g. `https://api-staging.yourschool.com` | e.g. `https://staging.yourschool.com` |
| **Production** | e.g. `https://api.yourschool.com` | e.g. `https://app.yourschool.com` |

---

## CORS and auth issuer by environment

- **CORS_ORIGINS** must list every origin that will call the API (browser). Use the frontend origin(s) for that environment. Multiple origins: comma-separated, no spaces (e.g. `https://app.example.com,https://staging.example.com`).
- **CLERK_JWT_ISSUER** must match the Clerk instance that issues JWTs for your app (same for staging vs prod if you use one Clerk app; different if you use separate Clerk instances per environment).

Example:

| Environment | CORS_ORIGINS | CLERK_JWT_ISSUER |
|--------------|--------------|-------------------|
| Staging | `https://staging.yourschool.com` | `https://your-clerk-instance.clerk.accounts.dev` |
| Production | `https://app.yourschool.com` | `https://your-clerk-instance.clerk.accounts.dev` |

---

## Quick checklist before deploy

- [ ] `DATABASE_URL` set and reachable from the API host.
- [ ] `APP_ENV=production` (or `prod`) for production API.
- [ ] `CORS_ORIGINS` set to the exact frontend origin(s), comma-separated.
- [ ] `CLERK_JWT_ISSUER` set to your Clerk issuer URL (production only).
- [ ] Frontend built with correct `VITE_API_URL` for the target API.
- [ ] Run smoke check after deploy: `python scripts/deploy_smoke_check.py --api-url <API_BASE_URL>`.
