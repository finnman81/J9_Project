# Deployment Guide

This project supports two deployment paths:

1. **Current production path** — FastAPI backend (`api/`) + React frontend (`web/`) with Docker and optional Clerk JWT auth.
2. **Legacy path** — Streamlit Community Cloud using `app.py` (optional).

---

## Current production path (FastAPI + React)

### Overview

- **Backend:** FastAPI in `api/`, run in production via Gunicorn (see repo root `Dockerfile`). The container binds to `PORT` when set (e.g. by the platform); otherwise defaults to 8080.
- **Frontend:** React + Vite + Tailwind in `web/`. Build with `npm run build` and serve the `web/dist` output as static files.

### Required environment

**API (backend)**

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (e.g. Supabase). |
| `CORS_ORIGINS` | Yes in production | Comma-separated allowlist of frontend origins (e.g. `https://app.example.com`). |
| `CLERK_JWT_ISSUER` | Yes in production | Clerk JWT issuer URL (e.g. `https://your-instance.clerk.accounts.dev`). |
| `APP_ENV` | Optional | Set to `production` or `prod` to enable production checks (CORS + auth required). |
| `PORT` | Optional | Port the server binds to (default 8080). Many clouds inject this. |

**Frontend (build-time)**

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes for remote API | Base URL of the API (e.g. `https://api.example.com`). Omit or use `http://localhost:8000` for local dev. |

### Build and run

**Backend (Docker)**

The repo `Dockerfile` includes a `HEALTHCHECK` that hits `/health` every 30s so orchestrators (Docker, Kubernetes, App Runner) can detect unhealthy containers.

```bash
docker build -t j9-api .
docker run -p 8080:8080 -e DATABASE_URL="..." -e CORS_ORIGINS="https://your-frontend.com" -e CLERK_JWT_ISSUER="https://..." -e APP_ENV=production j9-api
```

**Frontend (static build)**

```bash
cd web
npm ci
npm run build
# Serve the contents of web/dist with any static host (e.g. Amplify, Vercel, nginx).
```

For a full list of required env vars and staging vs production values, see [DEPLOY_CONFIG.md](DEPLOY_CONFIG.md). After deploying, you can run the smoke check: `python scripts/deploy_smoke_check.py --api-url https://your-api.example.com`.

---

## Legacy: Deploy to GitHub + Streamlit Community Cloud

Follow these steps to put this project under the **finnman81** GitHub account and deploy it to Streamlit (legacy path using `app.py`).

---

### 1. Create the GitHub repository (finnman81)

1. Log in to GitHub as **finnman81**: https://github.com/login  
2. Click **New repository** (or go to https://github.com/new).  
3. Set:
   - **Repository name**: e.g. `literacy-assessment-app` (or any name you prefer)
   - **Description**: e.g. `Literacy Assessment & Intervention Tracking System`
   - **Visibility**: **Public** (required for free Streamlit Community Cloud)
   - Leave "Add a README" **unchecked** (you already have one)
4. Click **Create repository**.

---

### 2. Push this project to the new repo

In a terminal, from this project folder (`J9_Project`):

```powershell
cd "c:\Users\jakef\Projects\J9_Project"

# Initialize git (if not already)
git init

# Add remote (replace REPO_NAME with your actual repo name, e.g. literacy-assessment-app)
git remote add origin https://github.com/finnman81/REPO_NAME.git

# Stage and commit
git add .
git commit -m "Initial commit: Literacy Assessment Streamlit app"

# Push (main branch)
git branch -M main
git push -u origin main
```

If the repo already had a `git init` and `origin`, use:

```powershell
git remote set-url origin https://github.com/finnman81/REPO_NAME.git
git add .
git commit -m "Initial commit: Literacy Assessment Streamlit app"
git push -u origin main
```

---

### 3. Deploy on Streamlit Community Cloud

1. Go to **https://share.streamlit.io** and sign in with GitHub (use **finnman81** if that’s the account that owns the repo).  
2. Click **"New app"** or **"Deploy an app"**.  
3. Choose:
   - **Repository**: `finnman81/REPO_NAME`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Click **Deploy**.  
5. Wait a few minutes. The app will build and then be available at a URL like:  
   `https://REPO_NAME-XXXXX.streamlit.app`

---

### 4. After deployment

- **Database**: The app uses SQLite in `database/literacy_assessments.db`. On Streamlit Cloud the filesystem is ephemeral, so data is reset when the app restarts. For persistent data you’d need to switch to a hosted database (e.g. PostgreSQL) or use Streamlit’s experimental persistent storage; for now the app will run and create a fresh DB on each deploy/restart.
- **Updates**: Push changes to `main` on GitHub; Streamlit will usually prompt to redeploy or you can trigger a redeploy from the app’s dashboard on share.streamlit.io.

---

### Quick reference (Streamlit)

| Step | Action |
|------|--------|
| 1 | Create a **public** repo at github.com as **finnman81** |
| 2 | `git init`, `git remote add origin`, `git add .`, `git commit`, `git push` |
| 3 | share.streamlit.io → New app → pick repo, branch `main`, file `app.py` → Deploy |
