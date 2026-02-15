"""
Unified Tier Assignment Engine.

Standardises support-tier assignment across Reading and Math so that every
dashboard, KPI, and student detail page uses the same logic.

Tier levels (canonical strings used everywhere):
  - 'Core (Tier 1)'
  - 'Strategic (Tier 2)'
  - 'Intensive (Tier 3)'
  - 'Unknown'
"""
from typing import Optional, Dict, List
import pandas as pd
import numpy as np

from core.benchmarks import (
    get_support_level,
    blend_dashboard_tiers,
)
from core.math_benchmarks import get_math_support_level
from core.erb_scoring import (
    summarize_erb_scores,
    get_latest_erb_tier,
    erb_stanine_to_tier,
)

# ---------------------------------------------------------------------------
# Canonical tier constants
# ---------------------------------------------------------------------------

TIER_CORE = 'Core (Tier 1)'
TIER_STRATEGIC = 'Strategic (Tier 2)'
TIER_INTENSIVE = 'Intensive (Tier 3)'
TIER_UNKNOWN = 'Unknown'

_TIER_RANK = {
    TIER_CORE: 1,
    TIER_STRATEGIC: 2,
    TIER_INTENSIVE: 3,
    TIER_UNKNOWN: 0,
}


def tier_from_risk_level(risk_level: Optional[str]) -> str:
    """Map the legacy risk_level (High/Medium/Low) to a canonical tier."""
    if risk_level == 'High':
        return TIER_INTENSIVE
    elif risk_level == 'Medium':
        return TIER_STRATEGIC
    elif risk_level == 'Low':
        return TIER_CORE
    return TIER_UNKNOWN


def tier_from_composite_score(score: Optional[float]) -> str:
    """Derive tier from the app's internal 0-100 composite score."""
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return TIER_UNKNOWN
    if score < 50:
        return TIER_INTENSIVE
    elif score < 70:
        return TIER_STRATEGIC
    return TIER_CORE


def get_unified_tier_for_student(
    score_row: Optional[pd.Series],
    erb_summaries: Optional[List[Dict]] = None,
    subject: str = 'Reading',
) -> str:
    """Compute a single canonical tier for one student + subject.

    Parameters
    ----------
    score_row : pandas Series (a row from literacy_scores or math_scores),
                or None if the student has no scores.
    erb_summaries : list of dicts from ``summarize_erb_scores()`` for this
                    student (Reading only; pass None for Math).
    subject : 'Reading' or 'Math'

    Returns
    -------
    One of TIER_CORE, TIER_STRATEGIC, TIER_INTENSIVE, TIER_UNKNOWN.
    """
    if score_row is None:
        return TIER_UNKNOWN

    # If we already stored a support_tier, honour it.
    stored_tier = score_row.get('support_tier')
    if stored_tier and stored_tier in _TIER_RANK and stored_tier != TIER_UNKNOWN:
        return stored_tier

    # Derive from risk_level (legacy path)
    risk = score_row.get('risk_level')
    base_tier = tier_from_risk_level(risk)

    if subject == 'Reading' and erb_summaries:
        erb_tier = get_latest_erb_tier(erb_summaries)
        return blend_dashboard_tiers(base_tier, erb_tier)

    return base_tier


def assign_tiers_bulk(
    students_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    assessments_df: Optional[pd.DataFrame] = None,
    subject: str = 'Reading',
    school_year: Optional[str] = None,
) -> pd.DataFrame:
    """Assign a canonical support tier to every student in bulk.

    Returns a DataFrame with columns:
        student_id, student_name, grade_level, teacher_name,
        overall_score, risk_level, support_tier, assessment_period

    Parameters
    ----------
    students_df   : students table rows
    scores_df     : literacy_scores or math_scores rows
    assessments_df: assessments table rows (needed for ERB tier blending in Reading)
    subject       : 'Reading' or 'Math'
    school_year   : optional filter
    """
    if school_year and 'school_year' in scores_df.columns:
        scores_df = scores_df[scores_df['school_year'] == school_year]

    # Order periods so we pick the latest
    period_order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
    score_col = 'overall_literacy_score' if subject == 'Reading' else 'overall_math_score'

    rows = []
    for _, stu in students_df.iterrows():
        sid = stu['student_id']
        stu_scores = scores_df[scores_df['student_id'] == sid]

        if stu_scores.empty:
            rows.append({
                'student_id': sid,
                'student_name': stu.get('student_name'),
                'grade_level': stu.get('grade_level'),
                'teacher_name': stu.get('teacher_name'),
                'overall_score': None,
                'risk_level': None,
                'support_tier': TIER_UNKNOWN,
                'assessment_period': None,
            })
            continue

        # Pick latest period
        if 'assessment_period' in stu_scores.columns:
            stu_scores = stu_scores.copy()
            stu_scores['_period_rank'] = stu_scores['assessment_period'].map(period_order).fillna(0)
            latest = stu_scores.sort_values('_period_rank', ascending=False).iloc[0]
        else:
            latest = stu_scores.iloc[-1]

        # ERB blending for Reading
        erb_sums = None
        if subject == 'Reading' and assessments_df is not None:
            stu_assess = assessments_df[assessments_df['student_id'] == sid]
            if not stu_assess.empty:
                erb_sums = summarize_erb_scores(stu_assess, stu.get('student_name', ''))

        tier = get_unified_tier_for_student(latest, erb_sums, subject)

        rows.append({
            'student_id': sid,
            'student_name': stu.get('student_name'),
            'grade_level': stu.get('grade_level'),
            'teacher_name': stu.get('teacher_name'),
            'overall_score': latest.get(score_col),
            'risk_level': latest.get('risk_level'),
            'support_tier': tier,
            'assessment_period': latest.get('assessment_period'),
        })

    return pd.DataFrame(rows)


def is_needs_support(tier: str) -> bool:
    """Return True if the tier indicates the student needs support."""
    return tier in (TIER_STRATEGIC, TIER_INTENSIVE)
