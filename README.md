# Literacy Assessment & Intervention Tracking System

A Streamlit-based web application for tracking student literacy assessments, calculating overall literacy scores, identifying intervention needs, and generating insights.

## Features

- **Overview Dashboard**: KPIs, interactive graphs, and sortable student table with filters
- **Student Detail Page**: Deep dive into individual student progress with visualizations
- **Grade Entry Page**: Flexible data entry supporting both single-student and bulk entry modes
- **Intervention Tracking**: Track interventions and their effectiveness
- **Automated Scoring**: Calculates overall literacy scores and risk levels automatically

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize the database:
```bash
python -c "from core.database import init_database; init_database()"
```

3. Migrate existing data (optional):
```bash
python scripts/migrate_data.py
```

## Running the Application

### Option 1: Streamlit (legacy)

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### Option 2: New Web App (React + FastAPI)

From the **ui-project** branch, you can run the production-style web app:

1. **Set database URL** (required for the API): copy `.env.example` to `.env` in the project root and set your `DATABASE_URL`:
   ```bash
   copy .env.example .env
   ```
   Then edit `.env` and set `DATABASE_URL=postgresql://...` (your Supabase or Postgres URL). The API loads `.env` automatically via python-dotenv. Alternatively set the `DATABASE_URL` environment variable in your shell. (Streamlit can still use `.streamlit/secrets.toml`.)

2. **Start the API** (from project root):
   ```bash
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Start the frontend** (in another terminal):
   ```bash
   cd web
   npm install
   npm run dev
   ```
   On PowerShell use `;` instead of `&&` if you combine commands (e.g. `cd web; npm run dev`).
   The app will be at `http://localhost:5173`. It proxies `/api` and `/health` to the API.

4. **Optional**: Copy `web/.env.example` to `web/.env` and set `VITE_API_URL` if the API is not on port 8000, or `VITE_THEME` to switch themes (default is `peck`).

## Database Schema

- **students**: Student information (name, grade, class, teacher)
- **assessments**: Assessment scores and data
- **interventions**: Intervention tracking
- **literacy_scores**: Calculated literacy scores and risk levels

## Usage

1. **Overview Dashboard**: View schoolwide metrics, filter by grade/class/teacher, see risk distributions
2. **Student Detail**: Select a student to see their complete progress, assessments, and interventions
3. **Grade Entry**: Enter new assessments (single or bulk) and track interventions

## Data Entry

- Single Student Entry: Form-based entry for one student at a time
- Bulk Entry: Upload CSV/Excel file with multiple students
- Download template CSV from the bulk entry page

## Deploy to Streamlit Community Cloud

1. Push this repo to a **public** GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and click **New app**.
3. Select your repo, branch `main`, and main file path **`app.py`**.

See **[DEPLOY.md](docs/DEPLOY.md)** for step-by-step instructions (including creating the repo under the finnman81 account).

## Documentation

- **[docs/](docs/)** – Design and deployment docs
- **[docs/STUDENT_DETAIL_DATA_AND_API.md](docs/STUDENT_DETAIL_DATA_AND_API.md)** – How the Student Detail page retrieves data (API) and displays it (frontend): endpoint, subject filtering, header KPIs, and fallbacks

## Notes

- SQLite database is stored in `database/literacy_assessments.db`
- Literacy scores are automatically recalculated when new assessments are added
- Original Excel data can be imported via `migrate_data.py`
- On Streamlit Cloud, the database is ephemeral (resets on app restart) unless you add a persistent database
