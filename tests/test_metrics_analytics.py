"""
Integration tests for metrics analytics endpoints used by the Analytics page.

Run with: pytest tests/test_metrics_analytics.py -v
Requires DATABASE_URL in .env (or environment). Skips if not set.
"""
import os

import pytest

try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_available():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    return True


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_root():
    import sys
    root = _root()
    if root not in sys.path:
        sys.path.insert(0, root)


def test_distribution_metrics_math(db_available):
    """Distribution endpoint returns avg_by_grade for Math (used by Analytics + Overview)."""
    _ensure_root()
    from core.database import get_v_support_status
    from api.routers.metrics import get_distribution

    # Ensure there is at least some Math data; otherwise skip
    df = get_v_support_status(subject_area="Math")
    if df is None or df.empty:
        pytest.skip("No Math rows in v_support_status")

    resp = get_distribution(subject="Math")
    assert isinstance(resp, dict)
    assert "avg_by_grade" in resp
    assert "bins" in resp


def test_support_trend_metrics_math(db_available):
    """Support-trend endpoint returns rows when there is tier data for Math."""
    _ensure_root()
    from core.database import get_v_support_status
    from api.routers.metrics import get_support_trend

    df = get_v_support_status(subject_area="Math")
    if df is None or df.empty:
        pytest.skip("No Math rows in v_support_status")

    resp = get_support_trend(subject="Math")
    assert isinstance(resp, dict)
    assert "rows" in resp
    rows = resp["rows"]
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert "school_year" in row and "pct_needs_support" in row


def test_assessment_averages_math(db_available):
    """Assessment-averages endpoint returns rows when there are normalized Math scores."""
    _ensure_root()
    from core.database import get_db_connection
    from api.routers.metrics import get_assessment_averages

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM assessments
            WHERE score_normalized IS NOT NULL AND subject_area = 'Math'
            LIMIT 1
            """
        )
        has_math = cur.fetchone() is not None
    finally:
        conn.close()

    if not has_math:
        pytest.skip("No Math assessments with score_normalized")

    resp = get_assessment_averages(subject="Math")
    assert isinstance(resp, dict)
    assert "rows" in resp
    rows = resp["rows"]
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert "assessment_type" in row and "average_score" in row

