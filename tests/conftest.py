"""
Pytest configuration and fixtures for integration tests.
Requires DATABASE_URL (e.g. from .env). Tests that need DB are skipped if not set.
"""
import os
import pytest

# Load .env so DATABASE_URL is available when running tests from project root
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that hit the real database (deselect with '-m \"not integration\"')")


@pytest.fixture(scope="session")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set; run with .env or set env to run integration tests")
    return url


@pytest.fixture(scope="session")
def sample_math_enrollment_id(db_url):
    """One enrollment_id that has at least one Math assessment (for tier/trend tests)."""
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from core.database import get_db_connection
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.enrollment_id FROM assessments a
            WHERE a.enrollment_id IS NOT NULL AND a.subject_area = 'Math'
            LIMIT 1
        """)
        row = cur.fetchone()
        return str(row[0]) if row else None
    finally:
        conn.close()
