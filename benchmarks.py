"""
Acadience Reading K-6 Benchmark Goals, Cut Points, and Analysis Utilities.

All benchmark data sourced from the publicly available Acadience Reading
Benchmark Goals handout (Dynamic Measurement Group / Acadience Learning).

Benchmark status levels:
  - Above Benchmark    (90-99% likelihood of meeting future goals)
  - At Benchmark       (70-85% likelihood)
  - Below Benchmark    (40-60% likelihood) → Strategic Support
  - Well Below Benchmark (10-20% likelihood) → Intensive Support
"""
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Grade-level helpers
# ---------------------------------------------------------------------------

GRADE_ALIASES = {
    'Kindergarten': 'K', 'kindergarten': 'K', 'K': 'K', 'k': 'K', '0': 'K',
    'First': '1', 'first': '1', '1': '1', '1st': '1',
    'Second': '2', 'second': '2', '2': '2', '2nd': '2',
    'Third': '3', 'third': '3', '3': '3', '3rd': '3',
    'Fourth': '4', 'fourth': '4', '4': '4', '4th': '4',
    'Fifth': '5', 'fifth': '5', '5': '5', '5th': '5',
    'Sixth': '6', 'sixth': '6', '6': '6', '6th': '6',
}

PERIOD_MAP = {
    'Fall': 'BOY', 'fall': 'BOY', 'BOY': 'BOY',
    'Winter': 'MOY', 'winter': 'MOY', 'MOY': 'MOY',
    'Spring': 'EOY', 'spring': 'EOY', 'EOY': 'EOY', 'eoy': 'EOY',
}


def _g(grade) -> Optional[str]:
    return GRADE_ALIASES.get(str(grade))


def _p(period) -> Optional[str]:
    return PERIOD_MAP.get(str(period))


# ---------------------------------------------------------------------------
# Benchmark reference data
# Key: (measure, grade, period) → (above_benchmark, benchmark_goal, cut_point_risk)
#   - score >= above_benchmark  → "Above Benchmark"
#   - score >= benchmark_goal   → "At Benchmark"
#   - score >= cut_point_risk   → "Below Benchmark"
#   - score <  cut_point_risk   → "Well Below Benchmark"
# ---------------------------------------------------------------------------

_BENCHMARKS: Dict[Tuple[str, str, str], Tuple[float, float, float]] = {
    # ── Reading Composite Score ───────────────────────────────────────────
    ('Composite', 'K', 'BOY'): (38, 26, 13),
    ('Composite', 'K', 'MOY'): (156, 122, 85),
    ('Composite', 'K', 'EOY'): (152, 119, 89),
    ('Composite', '1', 'BOY'): (129, 113, 97),
    ('Composite', '1', 'MOY'): (177, 130, 100),
    ('Composite', '1', 'EOY'): (208, 155, 111),
    ('Composite', '2', 'BOY'): (202, 141, 109),
    ('Composite', '2', 'MOY'): (256, 190, 145),
    ('Composite', '2', 'EOY'): (287, 238, 180),
    ('Composite', '3', 'BOY'): (289, 220, 180),
    ('Composite', '3', 'MOY'): (349, 285, 235),
    ('Composite', '3', 'EOY'): (405, 330, 280),
    ('Composite', '4', 'BOY'): (341, 290, 245),
    ('Composite', '4', 'MOY'): (383, 330, 290),
    ('Composite', '4', 'EOY'): (446, 391, 330),
    ('Composite', '5', 'BOY'): (386, 357, 258),
    ('Composite', '5', 'MOY'): (411, 372, 310),
    ('Composite', '5', 'EOY'): (466, 415, 340),
    ('Composite', '6', 'BOY'): (435, 344, 280),
    ('Composite', '6', 'MOY'): (461, 358, 285),
    ('Composite', '6', 'EOY'): (478, 380, 324),

    # ── First Sound Fluency (FSF) ─────────────────────────────────────────
    ('FSF', 'K', 'BOY'): (16, 10, 5),
    ('FSF', 'K', 'MOY'): (43, 30, 20),

    # ── Phoneme Segmentation Fluency (PSF) ────────────────────────────────
    ('PSF', 'K', 'MOY'): (44, 20, 10),
    ('PSF', 'K', 'EOY'): (56, 40, 25),
    ('PSF', '1', 'BOY'): (47, 40, 25),

    # ── Nonsense Word Fluency – Correct Letter Sounds (NWF-CLS) ──────────
    ('NWF-CLS', 'K', 'MOY'): (28, 17, 8),
    ('NWF-CLS', 'K', 'EOY'): (40, 28, 15),
    ('NWF-CLS', '1', 'BOY'): (34, 27, 18),
    ('NWF-CLS', '1', 'MOY'): (59, 43, 33),
    ('NWF-CLS', '1', 'EOY'): (81, 58, 47),
    ('NWF-CLS', '2', 'BOY'): (72, 54, 35),

    # ── Nonsense Word Fluency – Whole Words Read (NWF-WWR) ───────────────
    ('NWF-WWR', '1', 'BOY'): (4, 1, 0),
    ('NWF-WWR', '1', 'MOY'): (17, 8, 3),
    ('NWF-WWR', '1', 'EOY'): (25, 13, 6),
    ('NWF-WWR', '2', 'BOY'): (21, 13, 6),

    # ── Oral Reading Fluency – Words Correct (ORF) ───────────────────────
    ('ORF', '1', 'MOY'): (34, 23, 16),
    ('ORF', '1', 'EOY'): (67, 47, 32),
    ('ORF', '2', 'BOY'): (68, 52, 37),
    ('ORF', '2', 'MOY'): (91, 72, 55),
    ('ORF', '2', 'EOY'): (104, 87, 65),
    ('ORF', '3', 'BOY'): (90, 70, 55),
    ('ORF', '3', 'MOY'): (105, 86, 68),
    ('ORF', '3', 'EOY'): (118, 100, 80),
    ('ORF', '4', 'BOY'): (104, 90, 70),
    ('ORF', '4', 'MOY'): (121, 103, 79),
    ('ORF', '4', 'EOY'): (133, 115, 95),
    ('ORF', '5', 'BOY'): (121, 111, 96),
    ('ORF', '5', 'MOY'): (133, 120, 101),
    ('ORF', '5', 'EOY'): (143, 130, 105),
    ('ORF', '6', 'BOY'): (139, 107, 90),
    ('ORF', '6', 'MOY'): (141, 109, 92),
    ('ORF', '6', 'EOY'): (151, 120, 95),

    # ── Maze Adjusted Score ──────────────────────────────────────────────
    ('Maze', '3', 'BOY'): (11, 8, 5),
    ('Maze', '3', 'MOY'): (16, 11, 7),
    ('Maze', '3', 'EOY'): (23, 19, 14),
    ('Maze', '4', 'BOY'): (18, 15, 10),
    ('Maze', '4', 'MOY'): (20, 17, 12),
    ('Maze', '4', 'EOY'): (28, 24, 20),
    ('Maze', '5', 'BOY'): (21, 18, 12),
    ('Maze', '5', 'MOY'): (21, 20, 13),
    ('Maze', '5', 'EOY'): (28, 24, 18),
    ('Maze', '6', 'BOY'): (27, 18, 14),
    ('Maze', '6', 'MOY'): (30, 19, 14),
    ('Maze', '6', 'EOY'): (30, 21, 15),

    # ── Retell ───────────────────────────────────────────────────────────
    ('Retell', '1', 'MOY'): (17, 15, 0),
    ('Retell', '1', 'EOY'): (25, 16, 8),
    ('Retell', '2', 'BOY'): (25, 16, 8),
    ('Retell', '2', 'MOY'): (31, 21, 13),
    ('Retell', '2', 'EOY'): (39, 27, 18),
    ('Retell', '3', 'BOY'): (33, 20, 10),
    ('Retell', '3', 'MOY'): (40, 26, 18),
    ('Retell', '3', 'EOY'): (46, 30, 20),
    ('Retell', '4', 'BOY'): (36, 27, 14),
    ('Retell', '4', 'MOY'): (39, 30, 20),
    ('Retell', '4', 'EOY'): (46, 33, 24),
    ('Retell', '5', 'BOY'): (40, 33, 22),
    ('Retell', '5', 'MOY'): (46, 36, 25),
    ('Retell', '5', 'EOY'): (52, 36, 25),
    ('Retell', '6', 'BOY'): (43, 27, 16),
    ('Retell', '6', 'MOY'): (48, 29, 18),
    ('Retell', '6', 'EOY'): (50, 32, 24),
}

# All Acadience measure names supported
ACADIENCE_MEASURES = [
    'FSF', 'PSF', 'NWF-CLS', 'NWF-WWR', 'ORF', 'Maze', 'Retell', 'Composite',
]

# Human-readable measure names
MEASURE_LABELS = {
    'FSF': 'First Sound Fluency',
    'PSF': 'Phoneme Segmentation Fluency',
    'NWF-CLS': 'Nonsense Word Fluency (Letter Sounds)',
    'NWF-WWR': 'Nonsense Word Fluency (Whole Words)',
    'ORF': 'Oral Reading Fluency',
    'Maze': 'Maze Comprehension',
    'Retell': 'Retell Fluency',
    'Composite': 'Reading Composite Score',
}

# Measures applicable by grade (which measures are assessed at which grades)
MEASURES_BY_GRADE = {
    'K': ['FSF', 'PSF', 'NWF-CLS'],
    '1': ['PSF', 'NWF-CLS', 'NWF-WWR', 'ORF', 'Retell'],
    '2': ['NWF-CLS', 'NWF-WWR', 'ORF', 'Retell'],
    '3': ['ORF', 'Retell', 'Maze'],
    '4': ['ORF', 'Retell', 'Maze'],
    '5': ['ORF', 'Retell', 'Maze'],
    '6': ['ORF', 'Retell', 'Maze'],
}

# ── Approximate typical growth per period (BOY→MOY and MOY→EOY) ──────────
# Derived from published Acadience benchmark goals: typical growth ≈
# benchmark_goal(next_period) − benchmark_goal(current_period).
# Used for Pathways-of-Progress-lite growth classification.
# Key: (measure, grade, from_period, to_period) → expected_typical_growth
_TYPICAL_GROWTH: Dict[Tuple[str, str, str, str], float] = {}


def _build_typical_growth():
    """Pre-compute typical growth from benchmark goal deltas."""
    period_seq = ['BOY', 'MOY', 'EOY']
    for (measure, grade, period), (_, goal, _) in _BENCHMARKS.items():
        idx = period_seq.index(period) if period in period_seq else -1
        if idx < len(period_seq) - 1:
            next_period = period_seq[idx + 1]
            next_key = (measure, grade, next_period)
            if next_key in _BENCHMARKS:
                next_goal = _BENCHMARKS[next_key][1]
                _TYPICAL_GROWTH[(measure, grade, period, next_period)] = next_goal - goal


_build_typical_growth()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_benchmark_status(measure: str, grade, period, score: float) -> Optional[str]:
    """Return benchmark status for a given score.

    Returns one of: 'Above Benchmark', 'At Benchmark',
    'Below Benchmark', 'Well Below Benchmark', or None if no
    benchmark data exists for the combination.
    """
    g = _g(grade)
    p = _p(period)
    if g is None or p is None or score is None:
        return None
    key = (measure, g, p)
    if key not in _BENCHMARKS:
        return None
    above, goal, cut = _BENCHMARKS[key]
    if score >= above:
        return 'Above Benchmark'
    if score >= goal:
        return 'At Benchmark'
    if score >= cut:
        return 'Below Benchmark'
    return 'Well Below Benchmark'


def get_benchmark_thresholds(measure: str, grade, period) -> Optional[Dict[str, float]]:
    """Return benchmark thresholds for a measure/grade/period.

    Returns dict with keys: above_benchmark, benchmark_goal, cut_point_risk
    or None if no data.
    """
    g = _g(grade)
    p = _p(period)
    if g is None or p is None:
        return None
    key = (measure, g, p)
    if key not in _BENCHMARKS:
        return None
    above, goal, cut = _BENCHMARKS[key]
    return {
        'above_benchmark': above,
        'benchmark_goal': goal,
        'cut_point_risk': cut,
    }


def get_support_level(benchmark_status: Optional[str]) -> str:
    """Map benchmark status to instructional support level (tier).

    - At/Above Benchmark → Core (Tier 1)
    - Below Benchmark    → Strategic (Tier 2)
    - Well Below         → Intensive (Tier 3)
    """
    if benchmark_status in ('Above Benchmark', 'At Benchmark'):
        return 'Core (Tier 1)'
    elif benchmark_status == 'Below Benchmark':
        return 'Strategic (Tier 2)'
    elif benchmark_status == 'Well Below Benchmark':
        return 'Intensive (Tier 3)'
    return 'Unknown'


def classify_growth(measure: str, grade, from_period, to_period,
                    actual_growth: float) -> Optional[str]:
    """Classify growth rate relative to typical peers.

    Returns one of:
      'Well Above Typical', 'Above Typical', 'Typical',
      'Below Typical', 'Well Below Typical', or None.
    """
    g = _g(grade)
    fp = _p(from_period)
    tp = _p(to_period)
    if g is None or fp is None or tp is None:
        return None
    key = (measure, g, fp, tp)
    typical = _TYPICAL_GROWTH.get(key)
    if typical is None or typical == 0:
        return None
    ratio = actual_growth / typical
    if ratio >= 1.5:
        return 'Well Above Typical'
    elif ratio >= 1.15:
        return 'Above Typical'
    elif ratio >= 0.75:
        return 'Typical'
    elif ratio >= 0.4:
        return 'Below Typical'
    else:
        return 'Well Below Typical'


def growth_color(classification: Optional[str]) -> str:
    """Return a hex color for a growth classification."""
    return {
        'Well Above Typical': '#1a7431',
        'Above Typical': '#28a745',
        'Typical': '#17a2b8',
        'Below Typical': '#ffc107',
        'Well Below Typical': '#dc3545',
    }.get(classification, '#6c757d')


def benchmark_color(status: Optional[str]) -> str:
    """Return a hex color for a benchmark status."""
    return {
        'Above Benchmark': '#1a7431',
        'At Benchmark': '#28a745',
        'Below Benchmark': '#ffc107',
        'Well Below Benchmark': '#dc3545',
    }.get(status, '#6c757d')


def benchmark_emoji(status: Optional[str]) -> str:
    """Return an emoji for a benchmark status."""
    return {
        'Above Benchmark': '🟢',
        'At Benchmark': '🟢',
        'Below Benchmark': '🟡',
        'Well Below Benchmark': '🔴',
    }.get(status, '⚪')


def compute_aimline(baseline_score: float, target_score: float,
                    start_index: int, end_index: int,
                    num_points: int) -> List[float]:
    """Compute a straight aimline from baseline to target across num_points."""
    if num_points <= 1:
        return [baseline_score]
    step = (target_score - baseline_score) / (num_points - 1)
    return [baseline_score + step * i for i in range(num_points)]


def pm_trend_status(scores: List[float], aimline_values: List[float]) -> str:
    """Evaluate progress monitoring status from last 3 data points vs aimline.

    Returns: 'On Track', 'At Risk', 'Off Track'
    """
    if len(scores) < 3 or len(aimline_values) < 3:
        return 'Insufficient Data'
    last3 = scores[-3:]
    aim3 = aimline_values[-3:]
    above_count = sum(1 for s, a in zip(last3, aim3) if s >= a)
    if above_count >= 2:
        return 'On Track'
    elif above_count == 1:
        return 'At Risk'
    else:
        return 'Off Track'


def pm_status_color(status: str) -> str:
    return {'On Track': '#28a745', 'At Risk': '#ffc107', 'Off Track': '#dc3545'}.get(status, '#6c757d')


def group_students(students_df: pd.DataFrame, scores_df: pd.DataFrame,
                   measure: str = 'ORF') -> pd.DataFrame:
    """Group students into Core/Strategic/Intensive tiers.

    Parameters
    ----------
    students_df : DataFrame with student_id, student_name, grade_level
    scores_df   : DataFrame with student_id, assessment_period, and a column
                  matching *measure* (e.g. 'ORF' or 'overall_literacy_score')
    measure     : The Acadience measure to group by (or 'overall_literacy_score'
                  for the app's internal composite).

    Returns a DataFrame with columns:
        student_name, grade_level, score, benchmark_status, support_level, weakest_skill
    """
    rows = []
    for _, student in students_df.iterrows():
        sid = student['student_id']
        name = student['student_name']
        grade = student['grade_level']

        student_scores = scores_df[scores_df['student_id'] == sid]
        if student_scores.empty:
            rows.append({
                'student_name': name, 'grade_level': grade,
                'score': None, 'benchmark_status': None,
                'support_level': 'Unknown', 'weakest_skill': None,
            })
            continue

        latest = student_scores.iloc[-1]
        score = latest.get(measure) if measure in latest.index else latest.get('overall_literacy_score')
        period = latest.get('assessment_period', 'EOY')

        # Try Acadience benchmark first, fall back to internal thresholds
        status = get_benchmark_status(measure, grade, period, score)
        if status is None and score is not None:
            # Use internal literacy score thresholds
            if score >= 70:
                status = 'At Benchmark'
            elif score >= 50:
                status = 'Below Benchmark'
            else:
                status = 'Well Below Benchmark'

        support = get_support_level(status)

        # Identify weakest skill from component columns
        weakest = None
        component_cols = {
            'reading_component': 'Reading',
            'phonics_component': 'Phonics',
            'sight_words_component': 'Sight Words',
        }
        comp_scores = {}
        for col, label in component_cols.items():
            val = latest.get(col)
            if val is not None and pd.notna(val):
                comp_scores[label] = val
        if comp_scores:
            weakest = min(comp_scores, key=comp_scores.get)

        rows.append({
            'student_name': name,
            'grade_level': grade,
            'score': score,
            'benchmark_status': status,
            'support_level': support,
            'weakest_skill': weakest,
        })

    return pd.DataFrame(rows)


def generate_parent_report_html(student_name: str, grade: str, teacher: str,
                                school_year: str, period: str,
                                overall_score: float, risk_level: str,
                                components: Dict[str, float],
                                interventions: List[Dict],
                                goals: List[Dict] = None,
                                benchmark_status: str = None) -> str:
    """Generate a polished, one-page parent report as HTML."""

    status = benchmark_status or ('At Benchmark' if overall_score and overall_score >= 70
                                  else ('Below Benchmark' if overall_score and overall_score >= 50
                                        else 'Well Below Benchmark'))
    status_color = benchmark_color(status)
    support = get_support_level(status)

    score_display = f"{overall_score:.1f}" if overall_score is not None else "N/A"

    # Component rows
    comp_rows = ''
    comp_labels = {
        'reading_component': ('Reading', 'Ability to read and comprehend grade-level text'),
        'phonics_component': ('Phonics / Spelling', 'Knowledge of letter-sound relationships and spelling patterns'),
        'spelling_component': ('Spelling', 'Ability to spell words correctly'),
        'sight_words_component': ('Sight Words', 'Recognition of high-frequency words'),
    }
    for key, (label, description) in comp_labels.items():
        val = components.get(key)
        if val is not None:
            comp_status = 'On Track' if val >= 70 else ('Developing' if val >= 50 else 'Needs Support')
            comp_color = '#28a745' if val >= 70 else ('#ffc107' if val >= 50 else '#dc3545')
            comp_rows += f'''<tr>
                <td>{label}</td>
                <td style="text-align:center">{val:.1f}</td>
                <td style="text-align:center;color:{comp_color};font-weight:bold">{comp_status}</td>
                <td>{description}</td>
            </tr>'''

    # Intervention rows
    int_rows = ''
    if interventions:
        for inv in interventions[:5]:
            int_rows += f'''<tr>
                <td>{inv.get('intervention_type','')}</td>
                <td>{inv.get('status','')}</td>
                <td>{inv.get('start_date','')}</td>
            </tr>'''
    else:
        int_rows = '<tr><td colspan="3">No current interventions</td></tr>'

    # Goal rows
    goal_section = ''
    if goals:
        goal_rows = ''
        for g in goals[:3]:
            goal_rows += f'''<tr>
                <td>{g.get('measure','')}</td>
                <td>{g.get('baseline_score','')}</td>
                <td>{g.get('target_score','')}</td>
            </tr>'''
        goal_section = f'''
        <h2>Current Goals</h2>
        <table><tr><th>Area</th><th>Starting Score</th><th>Target Score</th></tr>
        {goal_rows}</table>'''

    # Suggestions based on support level
    suggestions = ''
    if support == 'Core (Tier 1)':
        suggestions = '''<ul>
            <li>Continue daily reading at home (15-20 minutes)</li>
            <li>Ask your child to retell stories in their own words</li>
            <li>Encourage writing about daily experiences</li>
        </ul>'''
    elif support == 'Strategic (Tier 2)':
        suggestions = '''<ul>
            <li>Read together daily for 20-30 minutes, pausing to discuss</li>
            <li>Practice sight words and spelling words regularly</li>
            <li>Ask questions about what your child reads to build comprehension</li>
            <li>Contact the teacher to discuss additional support strategies</li>
        </ul>'''
    else:
        suggestions = '''<ul>
            <li>Read aloud with your child for 20-30 minutes every day</li>
            <li>Practice letter sounds and word building activities</li>
            <li>Re-read familiar books to build fluency and confidence</li>
            <li>Schedule a meeting with the teacher to discuss an intervention plan</li>
            <li>Ask about supplemental programs or tutoring options</li>
        </ul>'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 1.5em 2em; color: #333; font-size: 14px; }}
  h1 {{ color: #1a3c5e; border-bottom: 3px solid #1a3c5e; padding-bottom: 6px; font-size: 22px; }}
  h2 {{ color: #1a3c5e; margin-top: 1.2em; font-size: 16px; }}
  .header-info {{ display: flex; justify-content: space-between; margin-bottom: 1em; }}
  .header-info div {{ flex: 1; }}
  .score-box {{ display: inline-block; padding: 12px 24px; border-radius: 8px;
                background: {status_color}; color: white; font-size: 28px;
                font-weight: bold; text-align: center; }}
  .status-label {{ display: inline-block; padding: 6px 16px; border-radius: 4px;
                   background: {status_color}20; color: {status_color};
                   font-weight: bold; margin-left: 12px; font-size: 16px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
  th {{ background: #f0f4f8; font-weight: bold; }}
  .footer {{ margin-top: 2em; padding-top: 1em; border-top: 1px solid #ccc;
             font-size: 11px; color: #888; }}
  ul {{ margin: 4px 0; padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
  @media print {{
    body {{ margin: 0.5em; font-size: 12px; }}
    .score-box {{ font-size: 22px; padding: 8px 16px; }}
  }}
</style></head><body>

<h1>Literacy Progress Report</h1>
<div class="header-info">
  <div><strong>Student:</strong> {student_name}</div>
  <div><strong>Grade:</strong> {grade}</div>
  <div><strong>Teacher:</strong> {teacher or 'N/A'}</div>
  <div><strong>Year:</strong> {school_year}</div>
  <div><strong>Period:</strong> {period}</div>
</div>

<h2>Overall Literacy Score</h2>
<p>
  <span class="score-box">{score_display}</span>
  <span class="status-label">{status}</span>
</p>
<p>Your child's overall literacy score is <strong>{score_display}</strong>, which places them in the
<strong>{status}</strong> range. Students in this range are recommended for
<strong>{support}</strong> instructional support.</p>

<h2>Skill Breakdown</h2>
<table>
  <tr><th>Skill Area</th><th>Score</th><th>Status</th><th>What This Measures</th></tr>
  {comp_rows if comp_rows else '<tr><td colspan="4">Component scores not available</td></tr>'}
</table>

{goal_section}

<h2>Current Interventions</h2>
<table>
  <tr><th>Intervention</th><th>Status</th><th>Start Date</th></tr>
  {int_rows}
</table>

<h2>How You Can Help at Home</h2>
{suggestions}

<div class="footer">
  <p>This report was generated on {pd.Timestamp.now().strftime('%B %d, %Y')}.
  For questions, please contact your child's teacher.
  Assessment benchmarks are based on Acadience Reading research standards.</p>
</div>

</body></html>'''

    return html
