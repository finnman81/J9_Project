# Project Organization

This document describes the folder structure of the project.

## Root Directory

The root directory contains:
- **Entry points**: `app.py` (main Streamlit app), `run.py` (quick start script)
- **Configuration**: `.gitignore`, `requirements.txt`
- **Documentation**: `README.md`

## Folder Structure

### `/core/`
Core application logic modules:
- `database.py` - Database connection and operations
- `calculations.py` - Reading/literacy score calculations
- `math_calculations.py` - Math score calculations
- `benchmarks.py` - Reading benchmark data and utilities
- `math_benchmarks.py` - Math benchmark data and utilities
- `erb_scoring.py` - ERB/CTP5 scoring utilities
- `utils.py` - Score recalculation utilities
- `visualizations.py` - Visualization helper functions
- `__init__.py` - Package initialization

### `/scripts/`
Utility and migration scripts:
- `migrate_data.py` - Data migration utilities
- `migrate_math_data.py` - Math data migration
- `migrate_sqlite_to_supabase.py` - SQLite to Supabase migration
- `normalize_grades.py` - Grade normalization utilities
- `generate_sample_data.py` - Sample data generation
- `generate_historical_data.py` - Historical data generation
- `generate_student_detail_data.py` - Student detail data generation
- `generate_sample_tier_trend_interventions_goals_notes.py` - Sample Tier/Risk (benchmark_thresholds), Trend (extra assessments), interventions (at-risk), goals, notes
- `update_support_tier_distribution.py` - Support tier updates

### `/schema/`
Database schema files:
- `supabase_schema.sql` - Main database schema
- `supabase_schema_math.sql` - Math-specific schema additions
- `enrollment_identity_migration.md` - Enrollment/student identity model (students_core, student_enrollments, student_id_map)

### `/docs/`
Documentation files:
- `DEPLOY.md` - Deployment instructions
- `SYSTEM_DESIGN.md` - System design documentation
- `STUDENT_DETAIL_DATA_AND_API.md` - How Student Detail data is retrieved (API) and displayed (frontend)
- `STUDENT_DETAIL_API_TRACE.md` - Student Detail API trace and troubleshooting
- `ORGANIZATION.md` - This file

### `/data/`
Data files and resources:
- Excel files (`.xlsx`)
- PDF documents
- Other data files

### `/api/`
FastAPI backend (used by the new web app on the **ui-project** branch):
- `main.py` — FastAPI app, CORS, routers
- `routers/` — students, assessments, interventions, dashboard, teacher
- `serializers.py` — JSON serialization for pandas/NumPy
- `requirements.txt` — fastapi, uvicorn, python-multipart

### `/web/`
React + TypeScript + Tailwind frontend (ui-project branch):
- `src/themes/` — theme contract, Peck theme, ThemeProvider
- `src/api/client.ts` — API client and types
- `src/components/` — Layout, RiskBadge
- `src/pages/` — OverviewDashboard, StudentDetail, GradeEntry, TeacherDashboard

### `/pages/`
Streamlit page modules:
- `grade_entry.py` - Grade entry page
- `overview_dashboard.py` - Reading overview dashboard
- `math_overview_dashboard.py` - Math overview dashboard
- `student_detail.py` - Reading student detail page
- `math_student_detail.py` - Math student detail page
- `teacher_dashboard.py` - Teacher dashboard

### `/math_build/`
Math-specific build files and resources:
- CSV files for math benchmarks
- Math information PDFs

### `/.streamlit/`
Streamlit configuration:
- `config.toml` - Streamlit app configuration

### `/database/`
Database-related files (currently contains `.gitkeep`)

## Import Patterns

All imports from core modules use the `core.` prefix:
```python
from core.database import get_db_connection
from core.calculations import process_assessment_score
from core.math_calculations import process_math_assessment_score
```

Scripts in `/scripts/` add the parent directory to `sys.path` to enable imports:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_connection
```

## Notes

- Core application logic files are organized in `/core/` for better structure
- Scripts are organized in `/scripts/` for utility functions
- Schema files are in `/schema/` for database management
- Documentation is centralized in `/docs/`
- Data files are stored in `/data/` to keep root clean
- Entry points (`app.py`, `run.py`) remain in root for easy access
