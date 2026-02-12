"""
One-time migration script: copies all data from local SQLite → Supabase (PostgreSQL).

Usage:
    python migrate_sqlite_to_supabase.py

Prerequisites:
    1. Your Supabase project exists and the schema has been created
       (run schema/supabase_schema.sql in the Supabase SQL Editor first).
    2. DATABASE_URL is set in .streamlit/secrets.toml or as an env var.
    3. The local SQLite file exists at database/literacy_assessments.db.
"""
import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys
import tomllib

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SQLITE_PATH = 'database/literacy_assessments.db'

# Tables in dependency order (parents before children)
TABLES = [
    'students',
    'assessments',
    'interventions',
    'literacy_scores',
    'teacher_notes',
    'student_goals',
]


def get_pg_url() -> str:
    """Read DATABASE_URL from Streamlit secrets or env."""
    # Try .streamlit/secrets.toml
    secrets_path = os.path.join('.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        with open(secrets_path, 'rb') as f:
            secrets = tomllib.load(f)
        url = secrets.get('DATABASE_URL')
        if url:
            return url
    # Fallback to env
    url = os.environ.get('DATABASE_URL')
    if url:
        return url
    print("ERROR: DATABASE_URL not found in .streamlit/secrets.toml or environment.")
    sys.exit(1)


def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite database not found at {SQLITE_PATH}. Nothing to migrate.")
        return

    # Connect to both databases
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_url = get_pg_url()
    pg_conn = psycopg2.connect(pg_url)
    pg_cur = pg_conn.cursor()

    total_rows = 0

    for table in TABLES:
        print(f"\nMigrating table: {table}")

        # Read all rows from SQLite
        try:
            rows = sqlite_conn.execute(f'SELECT * FROM {table}').fetchall()
        except sqlite3.OperationalError as e:
            print(f"  Skipping (table may not exist in SQLite): {e}")
            continue

        if not rows:
            print(f"  0 rows — skipping")
            continue

        columns = rows[0].keys()
        # Remove auto-generated primary key columns so Postgres SERIAL handles them
        pk_map = {
            'students': 'student_id',
            'assessments': 'assessment_id',
            'interventions': 'intervention_id',
            'literacy_scores': 'score_id',
            'teacher_notes': 'note_id',
            'student_goals': 'goal_id',
        }
        pk_col = pk_map.get(table)

        # We include the PK so that foreign keys stay consistent
        col_names = list(columns)
        placeholders = ', '.join(['%s'] * len(col_names))
        col_list = ', '.join(col_names)

        # Build the ON CONFLICT clause based on unique constraints
        conflict_clause = ''
        if table == 'students':
            conflict_clause = 'ON CONFLICT (student_name, grade_level, school_year) DO NOTHING'
        elif table == 'assessments':
            conflict_clause = 'ON CONFLICT (student_id, assessment_type, assessment_period, school_year) DO NOTHING'
        elif table == 'literacy_scores':
            conflict_clause = 'ON CONFLICT (student_id, school_year, assessment_period) DO NOTHING'

        insert_sql = f'INSERT INTO {table} ({col_list}) VALUES ({placeholders}) {conflict_clause}'

        # We need to allow explicit PK values so sequences stay in sync
        # Temporarily allow identity insert
        try:
            pg_cur.execute(f"ALTER TABLE {table} ALTER COLUMN {pk_col} DROP IDENTITY IF EXISTS")
        except Exception:
            pg_conn.rollback()
        # If column uses SERIAL, we just insert with explicit ID; that's fine.

        inserted = 0
        for row in rows:
            values = [row[c] for c in col_names]
            try:
                pg_cur.execute(insert_sql, values)
                inserted += 1
            except Exception as e:
                pg_conn.rollback()
                print(f"  Error inserting row: {e}")
                continue

        pg_conn.commit()
        print(f"  {inserted}/{len(rows)} rows inserted")
        total_rows += inserted

        # Reset the sequence so new inserts get IDs after the max existing
        if pk_col:
            try:
                pg_cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', '{pk_col}'), "
                    f"COALESCE((SELECT MAX({pk_col}) FROM {table}), 1))"
                )
                pg_conn.commit()
            except Exception as e:
                pg_conn.rollback()
                print(f"  Warning: could not reset sequence for {table}.{pk_col}: {e}")

    sqlite_conn.close()
    pg_conn.close()

    print(f"\n{'='*50}")
    print(f"Migration complete. {total_rows} total rows migrated.")
    print(f"{'='*50}")


if __name__ == '__main__':
    migrate()
