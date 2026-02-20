#!/usr/bin/env python3
"""Quick check: show Ameera's enrollments after cleanup."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import get_db_connection
import pandas as pd

conn = get_db_connection()
df = pd.read_sql_query(
    """
    SELECT s.display_name, e.grade_level, e.school_year, e.class_name
    FROM student_enrollments e
    JOIN students_core s ON s.student_uuid = e.student_uuid
    WHERE s.display_name = 'Ameera'
    ORDER BY e.school_year, e.grade_level
    """,
    conn,
)
conn.close()

print("Ameera's enrollments after cleanup:")
print(df.to_string(index=False))
print(f"\nTotal: {len(df)} enrollment(s)")
