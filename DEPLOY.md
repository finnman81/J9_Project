# Deploy to GitHub + Streamlit Community Cloud

Follow these steps to put this project under the **finnman81** GitHub account and deploy it to Streamlit.

---

## 1. Create the GitHub repository (finnman81)

1. Log in to GitHub as **finnman81**: https://github.com/login  
2. Click **New repository** (or go to https://github.com/new).  
3. Set:
   - **Repository name**: e.g. `literacy-assessment-app` (or any name you prefer)
   - **Description**: e.g. `Literacy Assessment & Intervention Tracking System`
   - **Visibility**: **Public** (required for free Streamlit Community Cloud)
   - Leave "Add a README" **unchecked** (you already have one)
4. Click **Create repository**.

---

## 2. Push this project to the new repo

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

## 3. Deploy on Streamlit Community Cloud

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

## 4. After deployment

- **Database**: The app uses SQLite in `database/literacy_assessments.db`. On Streamlit Cloud the filesystem is ephemeral, so data is reset when the app restarts. For persistent data you’d need to switch to a hosted database (e.g. PostgreSQL) or use Streamlit’s experimental persistent storage; for now the app will run and create a fresh DB on each deploy/restart.
- **Updates**: Push changes to `main` on GitHub; Streamlit will usually prompt to redeploy or you can trigger a redeploy from the app’s dashboard on share.streamlit.io.

---

## Quick reference

| Step | Action |
|------|--------|
| 1 | Create a **public** repo at github.com as **finnman81** |
| 2 | `git init`, `git remote add origin`, `git add .`, `git commit`, `git push` |
| 3 | share.streamlit.io → New app → pick repo, branch `main`, file `app.py` → Deploy |
