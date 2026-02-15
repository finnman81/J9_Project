"""
Data Quality / Health Reporting Engine.

Provides a single function that audits assessment and score data for
a given subject and school year, returning a structured health report
used by the Data Health panels on overview dashboards.
"""
from datetime import date, datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Default: students whose last assessment is older than this are "overdue"
DEFAULT_OVERDUE_DAYS = 90


def _safe_days_since(dt_val, ref: date) -> Optional[int]:
    if dt_val is None or (isinstance(dt_val, float) and np.isnan(dt_val)):
        return None
    try:
        if isinstance(dt_val, str):
            dt_val = pd.to_datetime(dt_val).date()
        if isinstance(dt_val, datetime):
            dt_val = dt_val.date()
        if isinstance(dt_val, date):
            return (ref - dt_val).days
    except Exception:
        pass
    return None


def compute_data_health(
    students_df: pd.DataFrame,
    assessments_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    subject: str = 'Reading',
    school_year: Optional[str] = None,
    current_period: Optional[str] = None,
    reference_date: Optional[date] = None,
    overdue_threshold_days: int = DEFAULT_OVERDUE_DAYS,
) -> Dict:
    """Audit data quality and return a health report dict.

    Returns
    -------
    dict with keys:
        total_students, assessed_count, assessed_pct,
        missing_scores_count, missing_scores_students,
        invalid_range_count, duplicate_count,
        null_vs_zero_issues,
        median_days_since_assessment, pct_overdue,
        overdue_threshold_days
    """
    if reference_date is None:
        reference_date = date.today()

    # --- filter data to subject / year ------------------------------------
    assess = assessments_df.copy() if assessments_df is not None and not assessments_df.empty else pd.DataFrame()
    scores = scores_df.copy() if scores_df is not None and not scores_df.empty else pd.DataFrame()

    if not assess.empty and 'subject_area' in assess.columns:
        assess = assess[assess['subject_area'] == subject]
    if not assess.empty and school_year and 'school_year' in assess.columns:
        assess = assess[assess['school_year'] == school_year]
    # Exclude drafts
    if not assess.empty and 'is_draft' in assess.columns:
        assess = assess[assess['is_draft'].fillna(0).astype(int) == 0]

    if not scores.empty and school_year and 'school_year' in scores.columns:
        scores = scores[scores['school_year'] == school_year]

    total_students = len(students_df['student_id'].unique()) if not students_df.empty else 0
    all_sids = set(students_df['student_id'].unique()) if total_students else set()

    # --- assessed count ---------------------------------------------------
    scored_sids = set(scores['student_id'].unique()) if not scores.empty else set()
    assessed_count = len(scored_sids & all_sids)
    assessed_pct = (assessed_count / total_students * 100) if total_students else 0.0

    # --- missing scores (students with no calculated score) ---------------
    missing_sids = all_sids - scored_sids
    missing_students: List[str] = []
    if missing_sids and not students_df.empty:
        missing_students = (
            students_df[students_df['student_id'].isin(missing_sids)]['student_name']
            .tolist()
        )

    # --- invalid range (score_normalized outside 0-100 or negative raw) ---
    invalid_range_count = 0
    if not assess.empty and 'score_normalized' in assess.columns:
        norm = assess['score_normalized'].dropna()
        invalid_range_count += int(((norm < 0) | (norm > 100)).sum())
    if not assess.empty and 'raw_score' in assess.columns:
        raw = assess['raw_score'].dropna()
        invalid_range_count += int((raw < 0).sum())

    # --- duplicates (same student/type/period/year appearing >1 time) -----
    duplicate_count = 0
    if not assess.empty:
        dup_cols = ['student_id', 'assessment_type', 'assessment_period', 'school_year']
        dup_cols = [c for c in dup_cols if c in assess.columns]
        if dup_cols:
            dup_df = assess.groupby(dup_cols).size().reset_index(name='cnt')
            duplicate_count = int((dup_df['cnt'] > 1).sum())

    # --- null vs zero issues (score_normalized == 0 but score_value empty) -
    null_vs_zero = 0
    if not assess.empty and 'score_normalized' in assess.columns:
        zero_norm = assess[assess['score_normalized'] == 0]
        if not zero_norm.empty and 'score_value' in zero_norm.columns:
            null_vs_zero = int(
                zero_norm['score_value'].apply(
                    lambda v: v is None or (isinstance(v, str) and v.strip() == '') or (isinstance(v, float) and np.isnan(v))
                ).sum()
            )

    # --- assessment freshness ---------------------------------------------
    days_list: List[int] = []
    if not assess.empty and 'assessment_date' in assess.columns:
        latest_per_student = (
            assess.dropna(subset=['assessment_date'])
            .groupby('student_id')['assessment_date']
            .max()
        )
        for sid in all_sids:
            dt_val = latest_per_student.get(sid)
            d = _safe_days_since(dt_val, reference_date)
            if d is not None:
                days_list.append(d)

    median_days = float(np.median(days_list)) if days_list else None
    overdue_count = sum(1 for d in days_list if d > overdue_threshold_days)
    pct_overdue = (overdue_count / total_students * 100) if total_students else 0.0

    return {
        'total_students': total_students,
        'assessed_count': assessed_count,
        'assessed_pct': round(assessed_pct, 1),
        'missing_scores_count': len(missing_sids),
        'missing_scores_students': missing_students,
        'invalid_range_count': invalid_range_count,
        'duplicate_count': duplicate_count,
        'null_vs_zero_issues': null_vs_zero,
        'median_days_since_assessment': round(median_days, 1) if median_days is not None else None,
        'pct_overdue': round(pct_overdue, 1),
        'overdue_threshold_days': overdue_threshold_days,
    }
