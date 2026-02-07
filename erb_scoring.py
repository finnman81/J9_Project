"""
ERB / CTP5 Norm-Referenced Assessment Scoring and Classification.

Provides stanine classification, percentile interpretation, growth
percentile analysis, and tier mapping for CTP5 subtests (grades 1-11).

Score Types
-----------
- Stanine (1-9):  1-3 Below Average, 4-6 Average, 7-9 Above Average
- Percentile Rank (1-99): position within the norm group
- Scale Score: cross-form / cross-level comparable score
- Growth Percentile (1-99): academic progress relative to peers
"""
from typing import Optional, Dict, List, Tuple
import pandas as pd

# ---------------------------------------------------------------------------
# CTP5 Subtests
# ---------------------------------------------------------------------------

ERB_SUBTESTS = [
    'ERB_Reading_Comp',
    'ERB_Vocabulary',
    'ERB_Writing_Mechanics',
    'ERB_Writing_Concepts',
    'ERB_Mathematics',
    'ERB_Verbal_Reasoning',
    'ERB_Quant_Reasoning',
]

ERB_SUBTEST_LABELS = {
    'ERB_Reading_Comp': 'Reading Comprehension',
    'ERB_Vocabulary': 'Vocabulary',
    'ERB_Writing_Mechanics': 'Writing Mechanics',
    'ERB_Writing_Concepts': 'Writing Concepts & Skills',
    'ERB_Mathematics': 'Mathematics',
    'ERB_Verbal_Reasoning': 'Verbal Reasoning',
    'ERB_Quant_Reasoning': 'Quantitative Reasoning',
}

ERB_SUBTEST_DESCRIPTIONS = {
    'ERB_Reading_Comp': 'Understanding and interpreting written text',
    'ERB_Vocabulary': 'Word knowledge and usage in context',
    'ERB_Writing_Mechanics': 'Grammar, punctuation, and sentence structure',
    'ERB_Writing_Concepts': 'Organization, development, and clarity in writing',
    'ERB_Mathematics': 'Problem solving, computation, and mathematical reasoning',
    'ERB_Verbal_Reasoning': 'Logical reasoning with language-based information',
    'ERB_Quant_Reasoning': 'Logical reasoning with numerical information',
}

# ---------------------------------------------------------------------------
# Stanine Classification
# ---------------------------------------------------------------------------

STANINE_BANDS = {
    1: 'Well Below Average',
    2: 'Below Average',
    3: 'Below Average',
    4: 'Average',
    5: 'Average',
    6: 'Average',
    7: 'Above Average',
    8: 'Above Average',
    9: 'Well Above Average',
}

# Approximate percentile ranges corresponding to each stanine
STANINE_PERCENTILE_RANGES = {
    1: (1, 4),
    2: (5, 11),
    3: (12, 23),
    4: (24, 40),
    5: (41, 60),
    6: (61, 77),
    7: (78, 89),
    8: (90, 96),
    9: (97, 99),
}


def classify_stanine(stanine: int) -> Optional[str]:
    """Return the classification band for a stanine (1-9).

    Returns one of: 'Well Below Average', 'Below Average', 'Average',
    'Above Average', 'Well Above Average', or None.
    """
    if stanine is None or not isinstance(stanine, (int, float)):
        return None
    stanine = int(stanine)
    return STANINE_BANDS.get(stanine)


def stanine_color(stanine: int) -> str:
    """Return a hex color for a stanine value."""
    if stanine is None:
        return '#6c757d'
    stanine = int(stanine)
    if stanine <= 3:
        return '#dc3545'  # red
    elif stanine <= 6:
        return '#ffc107'  # yellow / amber
    else:
        return '#28a745'  # green


def stanine_bg_color(stanine: int) -> str:
    """Return a lighter background color for stanine display."""
    if stanine is None:
        return '#f8f9fa'
    stanine = int(stanine)
    if stanine <= 3:
        return '#f8d7da'
    elif stanine <= 6:
        return '#fff3cd'
    else:
        return '#d4edda'


def stanine_emoji(stanine: int) -> str:
    """Return an emoji for a stanine value."""
    if stanine is None:
        return '⚪'
    stanine = int(stanine)
    if stanine <= 3:
        return '🔴'
    elif stanine <= 6:
        return '🟡'
    else:
        return '🟢'

# ---------------------------------------------------------------------------
# Percentile Classification
# ---------------------------------------------------------------------------


def classify_percentile(percentile: float) -> Optional[str]:
    """Classify a percentile rank into performance bands.

    Returns one of: 'Needs Support', 'Approaching', 'On Track', 'Exceeding'.
    """
    if percentile is None:
        return None
    percentile = float(percentile)
    if percentile < 25:
        return 'Needs Support'
    elif percentile < 50:
        return 'Approaching'
    elif percentile < 75:
        return 'On Track'
    else:
        return 'Exceeding'


def percentile_color(percentile: float) -> str:
    """Return a hex color for a percentile rank."""
    if percentile is None:
        return '#6c757d'
    percentile = float(percentile)
    if percentile < 25:
        return '#dc3545'
    elif percentile < 50:
        return '#ffc107'
    elif percentile < 75:
        return '#17a2b8'
    else:
        return '#28a745'

# ---------------------------------------------------------------------------
# Growth Percentile Classification
# ---------------------------------------------------------------------------


def classify_growth_percentile(growth_pct: float) -> Optional[str]:
    """Classify an ERB growth percentile (1-99).

    Returns one of: 'Below Expected Growth', 'Typical Growth',
    'Above Expected Growth'.
    """
    if growth_pct is None:
        return None
    growth_pct = float(growth_pct)
    if growth_pct < 35:
        return 'Below Expected Growth'
    elif growth_pct <= 65:
        return 'Typical Growth'
    else:
        return 'Above Expected Growth'


def growth_percentile_color(classification: Optional[str]) -> str:
    """Return a hex color for a growth percentile classification."""
    return {
        'Below Expected Growth': '#dc3545',
        'Typical Growth': '#17a2b8',
        'Above Expected Growth': '#28a745',
    }.get(classification, '#6c757d')

# ---------------------------------------------------------------------------
# Tier Mapping (aligned with Acadience tiers)
# ---------------------------------------------------------------------------


def erb_stanine_to_tier(stanine: int) -> str:
    """Map a stanine to an instructional support tier.

    - Stanines 1-3 → Intensive (Tier 3)
    - Stanines 4-5 → Strategic (Tier 2)
    - Stanines 6-9 → Core (Tier 1)
    """
    if stanine is None:
        return 'Unknown'
    stanine = int(stanine)
    if stanine <= 3:
        return 'Intensive (Tier 3)'
    elif stanine <= 5:
        return 'Strategic (Tier 2)'
    else:
        return 'Core (Tier 1)'


def erb_percentile_to_tier(percentile: float) -> str:
    """Map a percentile to an instructional support tier.

    - <25th → Intensive (Tier 3)
    - 25th-49th → Strategic (Tier 2)
    - 50th+ → Core (Tier 1)
    """
    if percentile is None:
        return 'Unknown'
    percentile = float(percentile)
    if percentile < 25:
        return 'Intensive (Tier 3)'
    elif percentile < 50:
        return 'Strategic (Tier 2)'
    else:
        return 'Core (Tier 1)'

# ---------------------------------------------------------------------------
# Score parsing helpers
# ---------------------------------------------------------------------------


def parse_erb_score_value(score_value: str) -> Dict[str, Optional[float]]:
    """Parse a composite ERB score string into components.

    We store ERB scores in the assessments table using a structured format:
      "stanine:5|percentile:62|scale:450|growth:55"

    Returns dict with keys: stanine, percentile, scale_score, growth_percentile.
    """
    result = {
        'stanine': None,
        'percentile': None,
        'scale_score': None,
        'growth_percentile': None,
    }
    if not score_value:
        return result

    for part in str(score_value).split('|'):
        part = part.strip()
        if ':' not in part:
            continue
        key, val = part.split(':', 1)
        key = key.strip().lower()
        try:
            num = float(val.strip())
        except (ValueError, TypeError):
            continue
        if key == 'stanine':
            result['stanine'] = int(num)
        elif key == 'percentile':
            result['percentile'] = num
        elif key in ('scale', 'scale_score'):
            result['scale_score'] = num
        elif key in ('growth', 'growth_percentile'):
            result['growth_percentile'] = num

    return result


def build_erb_score_value(stanine: int = None, percentile: float = None,
                          scale_score: float = None,
                          growth_percentile: float = None) -> str:
    """Build a structured ERB score string for storage."""
    parts = []
    if stanine is not None:
        parts.append(f"stanine:{int(stanine)}")
    if percentile is not None:
        parts.append(f"percentile:{percentile:.0f}")
    if scale_score is not None:
        parts.append(f"scale:{scale_score:.0f}")
    if growth_percentile is not None:
        parts.append(f"growth:{growth_percentile:.0f}")
    return '|'.join(parts)

# ---------------------------------------------------------------------------
# Blended tier (Acadience + ERB)
# ---------------------------------------------------------------------------

_TIER_RANK = {
    'Core (Tier 1)': 1,
    'Strategic (Tier 2)': 2,
    'Intensive (Tier 3)': 3,
    'Unknown': 4,
}

_RANK_TIER = {v: k for k, v in _TIER_RANK.items()}


def blend_tiers(acadience_tier: str, erb_tier: str) -> str:
    """Return the more intensive (conservative) of two tier assignments.

    If a student is Core on Acadience but Strategic on ERB, the blended
    result is Strategic — we err on the side of more support.
    """
    a_rank = _TIER_RANK.get(acadience_tier, 4)
    e_rank = _TIER_RANK.get(erb_tier, 4)
    # Higher rank number = more intensive; 4 = Unknown (ignored)
    if a_rank == 4:
        return erb_tier
    if e_rank == 4:
        return acadience_tier
    return _RANK_TIER.get(max(a_rank, e_rank), acadience_tier)

# ---------------------------------------------------------------------------
# Summary helpers for reports & display
# ---------------------------------------------------------------------------


def summarize_erb_scores(assessments_df: pd.DataFrame,
                         student_name: str) -> List[Dict]:
    """Extract and summarize all ERB scores for a student.

    Returns a list of dicts, one per subtest-period combination:
        {subtest, label, period, school_year, stanine, percentile,
         scale_score, growth_percentile, classification, tier}
    """
    erb_mask = assessments_df['assessment_type'].isin(ERB_SUBTESTS)
    erb_df = assessments_df[erb_mask].copy()

    if erb_df.empty:
        return []

    results = []
    for _, row in erb_df.iterrows():
        parsed = parse_erb_score_value(row.get('score_value', ''))
        stanine = parsed['stanine']
        classification = classify_stanine(stanine)
        tier = erb_stanine_to_tier(stanine)
        subtest = row['assessment_type']

        results.append({
            'subtest': subtest,
            'label': ERB_SUBTEST_LABELS.get(subtest, subtest),
            'period': row.get('assessment_period', ''),
            'school_year': row.get('school_year', ''),
            'grade_level': row.get('grade_level', ''),
            'stanine': stanine,
            'percentile': parsed['percentile'],
            'scale_score': parsed['scale_score'],
            'growth_percentile': parsed['growth_percentile'],
            'classification': classification,
            'tier': tier,
        })

    return results


def get_latest_erb_tier(erb_summaries: List[Dict]) -> str:
    """Get the most intensive tier across all ERB subtests for a student."""
    if not erb_summaries:
        return 'Unknown'
    tiers = [s['tier'] for s in erb_summaries if s.get('tier') != 'Unknown']
    if not tiers:
        return 'Unknown'
    ranks = [_TIER_RANK.get(t, 4) for t in tiers]
    return _RANK_TIER.get(max(ranks), 'Unknown')
