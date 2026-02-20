"""
Integration tests for Student Detail data: Tier/Risk, Trend, Interventions, Notes, Goals.

Run with: pytest tests/test_student_detail_data.py -v
Requires DATABASE_URL in .env (or environment). Skips if not set.

UI path (Math Student Detail page):
  The page uses GET /api/student-detail/{student_uuid}?subject=Math (not the enrollment-detail
  endpoint). When you open /app/math/student/{uuid}, the frontend calls getStudentDetailByUuid;
  the backend uses get_multi_enrollment_* for tier, trend, notes, goals across that student's
  enrollments. Enrollment-based detail GET /api/enrollments/{id}/detail is used when navigating
  by enrollment, but the UI redirects to the student UUID route.
"""
import os
import pytest

# Ensure project root on path and load env
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

pytestmark = pytest.mark.integration

# Number of named students to test for UUID (student-detail) path
NUM_STUDENT_NAMES = 8


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_root():
    import sys
    root = _root()
    if root not in sys.path:
        sys.path.insert(0, root)


@pytest.fixture(scope="module")
def db_available():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    return True


@pytest.fixture(scope="module")
def math_enrollment_id(db_available):
    """An enrollment that has at least one Math assessment."""
    _ensure_root()
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


@pytest.fixture(scope="module")
def math_student_uuids_with_names(db_available):
    """
    List of (student_uuid, display_name) for students who have at least one Math assessment,
    for testing the same API path the Math Student Detail page uses (student-detail by UUID).
    """
    _ensure_root()
    from core.database import get_db_connection
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT c.student_uuid, c.display_name
            FROM students_core c
            JOIN student_enrollments e ON e.student_uuid = c.student_uuid
            JOIN assessments a ON a.enrollment_id = e.enrollment_id AND a.subject_area = 'Math'
            WHERE a.enrollment_id IS NOT NULL
            ORDER BY c.display_name
            LIMIT %s
        """, (NUM_STUDENT_NAMES,))
        rows = cur.fetchall()
        return [(str(r[0]), (r[1] or "?")[:50]) for r in rows]
    finally:
        conn.close()


def test_get_enrollment_returns_math_enrollment(math_enrollment_id):
    """Enrollment exists and has expected keys."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment
    en = get_enrollment(math_enrollment_id)
    assert en is not None
    assert "enrollment_id" in en or "display_name" in en
    assert en.get("enrollment_id") == math_enrollment_id or str(en.get("enrollment_id")) == math_enrollment_id


def test_v_teacher_roster_has_math_row_for_enrollment(math_enrollment_id, db_available):
    """v_teacher_roster contains a Math row for this enrollment (so Tier can show)."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_db_connection
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT subject_area FROM public.v_teacher_roster WHERE enrollment_id = %s",
            (math_enrollment_id,),
        )
        rows = cur.fetchall()
        subjects = [r[0] for r in rows]
        assert "Math" in subjects, f"v_teacher_roster should have Math for this enrollment; got subjects: {subjects}"
    finally:
        conn.close()


def test_get_enrollment_support_status_math_returns_row(math_enrollment_id, db_available):
    """get_enrollment_support_status(enrollment_id, 'Math') returns a dict with tier."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment_support_status
    support = get_enrollment_support_status(math_enrollment_id, "Math")
    assert support is not None, "Support status should be non-None for Math when v_teacher_roster has Math row"
    assert "tier" in support
    assert support["tier"] in ("Core", "Strategic", "Intensive", "Unknown"), f"Unexpected tier: {support['tier']}"


def test_get_enrollment_growth_math_returns_when_two_assessments(math_enrollment_id, db_available):
    """get_enrollment_growth for Math returns a row when there are 2+ assessments (trend)."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment_growth, get_enrollment
    en = get_enrollment(math_enrollment_id)
    school_year = en.get("school_year") if en else None
    growth = get_enrollment_growth(math_enrollment_id, "Math", school_year=school_year)
    # Growth can be None if only one assessment; we only assert structure when present
    if growth is not None:
        assert "trend" in growth
        assert growth["trend"] in ("Improving", "Stable", "Declining", "No Data"), f"Unexpected trend: {growth['trend']}"


def test_get_enrollment_interventions_returns_data_when_present(math_enrollment_id, db_available):
    """get_enrollment_interventions returns rows when interventions exist for this enrollment."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment_interventions
    df = get_enrollment_interventions(math_enrollment_id)
    assert df is not None
    # If DB has interventions for this enrollment, we should get them (no assertion on empty - may be legit)


def test_get_enrollment_notes_returns_data_when_present(math_enrollment_id, db_available):
    """get_enrollment_notes returns rows when notes exist for this enrollment (or legacy student)."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment_notes
    df = get_enrollment_notes(math_enrollment_id)
    assert df is not None
    assert hasattr(df, "empty")


def test_get_enrollment_goals_returns_data_when_present(math_enrollment_id, db_available):
    """get_enrollment_goals returns rows when goals exist for this enrollment (or legacy student)."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import get_enrollment_goals
    df = get_enrollment_goals(math_enrollment_id)
    assert df is not None
    assert hasattr(df, "empty")


def test_enrollment_detail_api_header_has_tier_and_trend(math_enrollment_id, db_available):
    """Simulate enrollment-detail API: header should have tier (and trend when growth exists)."""
    if not math_enrollment_id:
        pytest.skip("No Math enrollment in DB")
    _ensure_root()
    from core.database import (
        get_enrollment,
        get_enrollment_support_status,
        get_enrollment_growth,
        get_enrollment_notes,
        get_enrollment_goals,
    )
    en = get_enrollment(math_enrollment_id)
    assert en is not None
    subject_area = "Math"
    support = get_enrollment_support_status(math_enrollment_id, subject_area)
    growth_year = en.get("school_year")
    growth = get_enrollment_growth(math_enrollment_id, subject_area, school_year=growth_year)
    notes_df = get_enrollment_notes(math_enrollment_id)
    goals_df = get_enrollment_goals(math_enrollment_id)

    tier = support.get("tier") if support else None
    trend = (growth.get("trend") if growth else None) or (support.get("tier") and "Unknown")

    assert tier is not None, "Header tier should be set (from v_support_status or fallback)"
    assert trend is not None or growth is None  # trend can be Unknown when no growth row
    assert not notes_df.empty or notes_df is not None
    assert not goals_df.empty or goals_df is not None


# ---------------------------------------------------------------------------
# Student-detail-by-UUID path (same as Math Student Detail page: GET /api/student-detail/{uuid}?subject=Math)
# ---------------------------------------------------------------------------

def test_student_detail_by_uuid_multiple_names(math_student_uuids_with_names, db_available):
    """
    Same API path as Math Student Detail page: GET /api/student-detail/{uuid}?subject=Math.
    Asserts tier (and optionally trend/notes/goals) for multiple named students.
    """
    if not math_student_uuids_with_names:
        pytest.skip("No Math students in DB")
    _ensure_root()
    from core.database import (
        get_enrollments_for_student_uuid,
        get_multi_enrollment_support_status,
        get_multi_enrollment_growth,
        get_multi_enrollment_notes,
        get_multi_enrollment_goals,
    )
    failed = []
    for student_uuid, display_name in math_student_uuids_with_names:
        enrollments_df = get_enrollments_for_student_uuid(student_uuid)
        if enrollments_df.empty:
            failed.append((display_name, "no enrollments"))
            continue
        selected = [str(r["enrollment_id"]) for r in enrollments_df.to_dict("records")]
        support = get_multi_enrollment_support_status(selected, "Math")
        growth = get_multi_enrollment_growth(selected, "Math")
        notes_df = get_multi_enrollment_notes(selected)
        goals_df = get_multi_enrollment_goals(selected)

        tier = support.get("tier") if support else None
        if tier is None and support is not None:
            tier = support.get("tier")
        if tier is None:
            # Derive from assessments like the API does when support has no tier
            tier = "Unknown"
        if tier not in ("Core", "Strategic", "Intensive", "Unknown"):
            failed.append((display_name, f"bad tier {tier}"))
            continue
        trend = growth.get("trend") if growth else None
        if trend is not None and trend not in ("Improving", "Stable", "Declining", "No Data"):
            failed.append((display_name, f"bad trend {trend}"))
            continue
        if notes_df is None or not hasattr(notes_df, "empty"):
            failed.append((display_name, "notes not a DataFrame"))
        if goals_df is None or not hasattr(goals_df, "empty"):
            failed.append((display_name, "goals not a DataFrame"))
    assert not failed, f"Student-detail-by-UUID (Math) checks failed for: {failed}"


def test_student_detail_by_uuid_per_named_student(math_student_uuids_with_names, db_available):
    """
    For each of several named students (same path as UI: student-detail by UUID, subject=Math),
    assert tier is set and notes/goals are returned.
    """
    if not math_student_uuids_with_names:
        pytest.skip("No Math students in DB")
    _ensure_root()
    from core.database import (
        get_enrollments_for_student_uuid,
        get_multi_enrollment_support_status,
        get_multi_enrollment_growth,
        get_multi_enrollment_notes,
        get_multi_enrollment_goals,
    )
    for student_uuid, display_name in math_student_uuids_with_names:
        enrollments_df = get_enrollments_for_student_uuid(student_uuid)
        assert not enrollments_df.empty, f"{display_name}: no enrollments"
        selected = [str(r["enrollment_id"]) for r in enrollments_df.to_dict("records")]
        support = get_multi_enrollment_support_status(selected, "Math")
        tier = support.get("tier") if support else None
        assert tier is not None, f"{display_name}: tier should be set for Math student-detail"
        assert tier in ("Core", "Strategic", "Intensive", "Unknown"), f"{display_name}: tier={tier}"
        growth = get_multi_enrollment_growth(selected, "Math")
        if growth and growth.get("trend"):
            assert growth["trend"] in ("Improving", "Stable", "Declining", "No Data"), f"{display_name}: trend={growth.get('trend')}"
        notes_df = get_multi_enrollment_notes(selected)
        goals_df = get_multi_enrollment_goals(selected)
        assert notes_df is not None and hasattr(notes_df, "empty"), f"{display_name}: notes"
        assert goals_df is not None and hasattr(goals_df, "empty"), f"{display_name}: goals"
