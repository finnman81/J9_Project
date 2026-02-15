"""
Period-Aware Growth Calculation Engine.

Centralises all growth metric computation so that dashboards, detail
pages, and the priority engine use a single source of truth.
"""
from typing import Dict, Optional

import numpy as np
import pandas as pd

from core.benchmarks import classify_growth as _classify_reading_growth
from core.math_benchmarks import classify_math_growth as _classify_math_growth

# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

PERIOD_ORDER = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}

_PREV_PERIOD = {
    'Winter': 'Fall',
    'Spring': 'Winter',
    'EOY': 'Spring',
}


def previous_period(period: str) -> Optional[str]:
    """Return the period immediately before *period*, or None for Fall."""
    return _PREV_PERIOD.get(period)


# ---------------------------------------------------------------------------
# Per-student growth
# ---------------------------------------------------------------------------

def compute_period_growth(
    scores_df: pd.DataFrame,
    subject: str = 'Reading',
    from_period: str = 'Fall',
    to_period: str = 'Winter',
    school_year: Optional[str] = None,
) -> pd.DataFrame:
    """Compute per-student growth between two assessment periods.

    Returns a DataFrame with columns:
        student_id, from_score, to_score, growth_points,
        growth_classification (Improving/Stable/Declining)
    """
    score_col = 'overall_literacy_score' if subject == 'Reading' else 'overall_math_score'

    df = scores_df.copy()
    if school_year and 'school_year' in df.columns:
        df = df[df['school_year'] == school_year]

    from_scores = (
        df[df['assessment_period'] == from_period]
        .groupby('student_id')[score_col]
        .last()
        .rename('from_score')
    )
    to_scores = (
        df[df['assessment_period'] == to_period]
        .groupby('student_id')[score_col]
        .last()
        .rename('to_score')
    )

    merged = pd.concat([from_scores, to_scores], axis=1).dropna()
    if merged.empty:
        return pd.DataFrame(columns=[
            'student_id', 'from_score', 'to_score',
            'growth_points', 'growth_classification',
        ])

    merged['growth_points'] = merged['to_score'] - merged['from_score']

    # Classification using the 5-point threshold consistent with existing trend logic
    def _classify(pts):
        if pts > 5:
            return 'Improving'
        elif pts < -5:
            return 'Declining'
        return 'Stable'

    merged['growth_classification'] = merged['growth_points'].apply(_classify)
    merged = merged.reset_index()

    return merged[['student_id', 'from_score', 'to_score',
                    'growth_points', 'growth_classification']]


# ---------------------------------------------------------------------------
# Cohort summary
# ---------------------------------------------------------------------------

def compute_cohort_growth_summary(growth_df: pd.DataFrame) -> Dict:
    """Summarise growth across a cohort (grade, class, teacher, or whole school).

    Parameters
    ----------
    growth_df : output of ``compute_period_growth``

    Returns
    -------
    dict with: median_growth, mean_growth, pct_improving, pct_declining, pct_stable, n
    """
    if growth_df.empty or 'growth_points' not in growth_df.columns:
        return {
            'median_growth': None,
            'mean_growth': None,
            'pct_improving': 0.0,
            'pct_declining': 0.0,
            'pct_stable': 0.0,
            'n': 0,
        }

    pts = growth_df['growth_points'].dropna()
    n = len(pts)
    if n == 0:
        return {
            'median_growth': None,
            'mean_growth': None,
            'pct_improving': 0.0,
            'pct_declining': 0.0,
            'pct_stable': 0.0,
            'n': 0,
        }

    clf = growth_df['growth_classification']
    return {
        'median_growth': round(float(pts.median()), 1),
        'mean_growth': round(float(pts.mean()), 1),
        'pct_improving': round((clf == 'Improving').sum() / n * 100, 1),
        'pct_declining': round((clf == 'Declining').sum() / n * 100, 1),
        'pct_stable': round((clf == 'Stable').sum() / n * 100, 1),
        'n': n,
    }


# ---------------------------------------------------------------------------
# Acadience-measure-level growth (for student detail pages)
# ---------------------------------------------------------------------------

def classify_measure_growth(
    measure: str,
    grade,
    from_period: str,
    to_period: str,
    actual_growth: float,
    subject: str = 'Reading',
) -> Optional[str]:
    """Classify growth on a specific Acadience measure using published norms.

    Returns one of: 'Well Above Typical', 'Above Typical', 'Typical',
    'Below Typical', 'Well Below Typical', or None.
    """
    if subject == 'Reading':
        return _classify_reading_growth(measure, grade, from_period, to_period, actual_growth)
    else:
        return _classify_math_growth(measure, grade, from_period, to_period, actual_growth)
