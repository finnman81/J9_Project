"""
Priority Students Engine.

Dynamically ranks students by urgency so dashboards can surface the
students who most need attention right now.

Priority scoring factors (weighted sum, higher = more urgent):
  1. Tier weight: Intensive = 3, Strategic = 2, Core = 0
  2. No active intervention: +3 if Intensive/Strategic without one
  3. Declining growth trend: +2
  4. Stale assessment: +2 if >90 days, +1 if >60 days
  5. No growth data: +1 if trend is Unknown / insufficient data
"""
from datetime import datetime, date
from typing import List, Optional

import numpy as np
import pandas as pd

from core.tier_engine import (
    TIER_CORE,
    TIER_INTENSIVE,
    TIER_STRATEGIC,
    TIER_UNKNOWN,
    assign_tiers_bulk,
    is_needs_support,
)

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_TIER_WEIGHT = {
    TIER_INTENSIVE: 3,
    TIER_STRATEGIC: 2,
    TIER_CORE: 0,
    TIER_UNKNOWN: 0,
}

_NO_INTERVENTION_PENALTY = 3
_DECLINING_PENALTY = 2
_STALE_90_PENALTY = 2
_STALE_60_PENALTY = 1
_NO_GROWTH_DATA_PENALTY = 1

# Thresholds (days)
_STALE_THRESHOLD_HIGH = 90
_STALE_THRESHOLD_MED = 60


def _days_since(dt_val, reference: date) -> Optional[int]:
    """Compute days between *dt_val* and *reference*. Returns None on bad data."""
    if dt_val is None or (isinstance(dt_val, float) and np.isnan(dt_val)):
        return None
    if isinstance(dt_val, str):
        try:
            dt_val = pd.to_datetime(dt_val).date()
        except Exception:
            return None
    if isinstance(dt_val, datetime):
        dt_val = dt_val.date()
    if isinstance(dt_val, date):
        return (reference - dt_val).days
    return None


def compute_priority_students(
    students_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    interventions_df: pd.DataFrame,
    assessments_df: pd.DataFrame,
    subject: str = 'Reading',
    school_year: Optional[str] = None,
    current_period: Optional[str] = None,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """Return a ranked DataFrame of priority students.

    Columns returned:
        student_id, student_name, grade_level, teacher_name,
        support_tier, has_active_intervention, days_since_last_assessment,
        growth_trend, priority_score, priority_reasons
    """
    if reference_date is None:
        reference_date = date.today()

    # --- 1. Assign tiers --------------------------------------------------
    tiered = assign_tiers_bulk(
        students_df, scores_df, assessments_df, subject, school_year,
    )

    # --- 2. Active interventions ------------------------------------------
    if interventions_df is not None and not interventions_df.empty:
        active = interventions_df[interventions_df['status'] == 'Active']
        if 'subject_area' in active.columns:
            subj_active = active[
                (active['subject_area'] == subject) | active['subject_area'].isna()
            ]
        else:
            subj_active = active
        active_ids = set(subj_active['student_id'].unique())
    else:
        active_ids = set()

    # --- 3. Assessment freshness ------------------------------------------
    if assessments_df is not None and not assessments_df.empty:
        subj_assess = assessments_df
        if 'subject_area' in subj_assess.columns:
            subj_assess = subj_assess[subj_assess['subject_area'] == subject]
        if school_year and 'school_year' in subj_assess.columns:
            subj_assess = subj_assess[subj_assess['school_year'] == school_year]
        # Exclude drafts
        if 'is_draft' in subj_assess.columns:
            subj_assess = subj_assess[subj_assess['is_draft'].fillna(0).astype(int) == 0]

        if 'assessment_date' in subj_assess.columns:
            latest_dates = (
                subj_assess.dropna(subset=['assessment_date'])
                .groupby('student_id')['assessment_date']
                .max()
            )
        else:
            latest_dates = pd.Series(dtype='datetime64[ns]')
    else:
        latest_dates = pd.Series(dtype='datetime64[ns]')

    # --- 4. Growth trend from scores table --------------------------------
    trend_map: dict = {}
    if not scores_df.empty and 'trend' in scores_df.columns:
        period_order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        _tmp = scores_df.copy()
        if school_year and 'school_year' in _tmp.columns:
            _tmp = _tmp[_tmp['school_year'] == school_year]
        if 'assessment_period' in _tmp.columns:
            _tmp['_po'] = _tmp['assessment_period'].map(period_order).fillna(0)
            latest_trend = _tmp.sort_values('_po', ascending=False).groupby('student_id').first()
            trend_map = latest_trend['trend'].to_dict()

    # --- 5. Score each student -------------------------------------------
    rows = []
    for _, row in tiered.iterrows():
        sid = row['student_id']
        tier = row['support_tier']
        has_intervention = sid in active_ids
        trend = trend_map.get(sid, 'Unknown')

        # Days since last assessment
        last_date = latest_dates.get(sid)
        days_since = _days_since(last_date, reference_date)

        # Priority score
        score = _TIER_WEIGHT.get(tier, 0)
        reasons: List[str] = []

        if tier == TIER_INTENSIVE:
            reasons.append('Intensive tier')
        elif tier == TIER_STRATEGIC:
            reasons.append('Strategic tier')

        if is_needs_support(tier) and not has_intervention:
            score += _NO_INTERVENTION_PENALTY
            reasons.append(f'{tier.split(" ")[0]} without active intervention')

        if trend == 'Declining':
            score += _DECLINING_PENALTY
            reasons.append('Declining growth trend')
        elif trend == 'Unknown':
            score += _NO_GROWTH_DATA_PENALTY
            reasons.append('No growth data available')

        if days_since is not None:
            if days_since > _STALE_THRESHOLD_HIGH:
                score += _STALE_90_PENALTY
                reasons.append(f'Assessment overdue ({days_since} days)')
            elif days_since > _STALE_THRESHOLD_MED:
                score += _STALE_60_PENALTY
                reasons.append(f'Assessment aging ({days_since} days)')
        elif is_needs_support(tier):
            # No assessment date at all for at-risk student
            score += _STALE_90_PENALTY
            reasons.append('No assessment date on record')

        rows.append({
            'student_id': sid,
            'student_name': row.get('student_name'),
            'grade_level': row.get('grade_level'),
            'teacher_name': row.get('teacher_name'),
            'support_tier': tier,
            'has_active_intervention': has_intervention,
            'days_since_last_assessment': days_since,
            'growth_trend': trend,
            'priority_score': score,
            'priority_reasons': reasons,
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values('priority_score', ascending=False).reset_index(drop=True)
    return result


def get_top_priority(priority_df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Return the top *n* highest-priority students (score > 0 only)."""
    flagged = priority_df[priority_df['priority_score'] > 0]
    return flagged.head(n)
