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

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

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

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions (including creating the repo under the finnman81 account).

## Notes

- SQLite database is stored in `database/literacy_assessments.db`
- Literacy scores are automatically recalculated when new assessments are added
- Original Excel data can be imported via `migrate_data.py`
- On Streamlit Cloud, the database is ephemeral (resets on app restart) unless you add a persistent database
