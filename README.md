# School Assessment System

A web application for tracking student reading and math assessments, calculating scores and risk levels, identifying intervention needs, and generating insights. Built with **React (Vite)** frontend and **FastAPI** backend, with PostgreSQL/Supabase database. Also includes a legacy Streamlit app.

## Features

The app is organized by **subject** (Reading and Math), with the same pages available for each:

- **Overview Dashboard**: Schoolwide KPIs (assessed count, overdue, tier movement), score distribution histogram, average score by grade chart, and sortable/filterable student table showing support status, tier, trend, and priority scores
- **Student Detail**: Individual student view with summary KPIs (latest score, tier/risk, trend, last assessed, intervention status, goal status), score-over-time chart, and tables for assessments, interventions, notes, and goals (with enrollment filtering)
- **Grade Entry**: Form-based entry for single assessments or bulk upload via CSV/Excel
- **Analytics**: Deeper analytics including average score by grade (with units and grade order); additional analytics (norm comparison, multi-year trends, assessment-type breakdowns) are placeholders for future backend endpoints
- **Intervention Tracking**: Track interventions by subject with start dates, status, and notes
- **Automated Scoring**: Calculates overall scores, risk levels, and tier assignments (Core/Strategic/Intensive) automatically from assessment data

## Installation

See **Quick Start** section above for full setup instructions. Summary:

1. Install Python dependencies: `pip install -r requirements.txt`
2. Install frontend dependencies: `cd web && npm install`
3. Configure database URL in `.env`
4. Initialize database schema (if needed): `python -c "from core.database import init_database; init_database()"`

For migrating existing data, see `scripts/migrate_data.py` and other scripts in `scripts/`.

## Quick Start (React + FastAPI)

### Prerequisites

- **Python 3.8+** with `pip`
- **Node.js 16+** with `npm`
- **PostgreSQL database** (Supabase or local) with connection URL

### Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install frontend dependencies:**
   ```bash
   cd web
   npm install
   cd ..
   ```

3. **Configure database connection:**
   - Copy `.env.example` to `.env` in the project root
   - Edit `.env` and set your `DATABASE_URL`:
     ```
     DATABASE_URL=postgresql://user:password@host:port/database
     ```
   - Or set `DATABASE_URL` as an environment variable in your shell

4. **Initialize database schema** (if needed):
   ```bash
   python -c "from core.database import init_database; init_database()"
   ```

### Launch the Application

**You need two terminals running simultaneously:**

**Terminal 1 - Start the API server:**
```bash
uvicorn api.main:app --reload --port 8000
```
The API will be available at `http://localhost:8000` (and `/docs` for API documentation).

**Terminal 2 - Start the frontend:**
```bash
cd web
npm run dev
```
The app will open in your browser at `http://localhost:5173`. The frontend automatically proxies `/api` requests to the backend on port 8000.

**Note:** On Windows PowerShell, use `;` instead of `&&` if combining commands (e.g., `cd web; npm run dev`).

### Optional Frontend Configuration

Copy `web/.env.example` to `web/.env` and customize:
- `VITE_API_URL` - if the API is not on `http://localhost:8000`
- `VITE_THEME` - theme name (default: `peck`)

---

## Legacy: Streamlit App

The original Streamlit app is still available:

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Uses `.streamlit/secrets.toml` for database configuration.

## Database Schema

The app uses PostgreSQL (Supabase) with enrollment-based identity:

- **students_core**: Student UUIDs and display names
- **student_enrollments**: One row per student per grade/year/class (enrollment_id)
- **assessments**: Assessment scores linked to enrollments and subjects (Reading/Math)
- **interventions**: Intervention tracking linked to enrollments
- **student_goals**: Goals linked to enrollments
- **teacher_notes**: Notes linked to enrollments
- **v_support_status**: View computing tier (Core/Strategic/Intensive) from benchmark thresholds
- **v_growth_last_two**: View computing trend (Improving/Stable/Declining) from last two assessments

See `schema/` directory for full schema definitions and migrations.

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

- **Database**: Uses PostgreSQL/Supabase (not SQLite). Connection string configured via `DATABASE_URL` in `.env`
- **Scores and tiers**: Automatically calculated from assessments via SQL views (`v_support_status`, `v_growth_last_two`)
- **Sample data**: Run `scripts/generate_sample_tier_trend_interventions_goals_notes.py` to populate benchmark thresholds, trends, interventions, goals, and notes for all students
- **Data migration**: Original Excel/SQLite data can be imported via `scripts/migrate_data.py` and related migration scripts
