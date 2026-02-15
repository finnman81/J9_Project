"""
Acadience Math K-6 Benchmark Goals, Cut Points, and Analysis Utilities.

Benchmark data extracted from Acadience Math Assessment Manual and CSV files.
Note: Math Composite Score is NOT comparable across different grades or times of year.
However, benchmark status levels (Above/At/Below/Well Below) CAN be compared.

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
# Grade-level helpers (same as benchmarks.py)
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
# Extracted from CSV files and Acadience Math Assessment Manual
# ---------------------------------------------------------------------------

_MATH_BENCHMARKS: Dict[Tuple[str, str, str], Tuple[float, float, float]] = {
    # ── Math Composite Score ───────────────────────────────────────────────
    # Note: Composite scores are NOT comparable across grades/times
    # But benchmark STATUS levels are comparable
    ('Math_Composite', '1', 'BOY'): (148, 124, 81),
    ('Math_Composite', '1', 'MOY'): (148, 124, 81),
    ('Math_Composite', '1', 'EOY'): (53, 46, 33),
    ('Math_Composite', '2', 'BOY'): (32, 24, 16),
    ('Math_Composite', '2', 'MOY'): (57, 46, 45),
    ('Math_Composite', '2', 'EOY'): (57, 46, 45),
    
    # ── Number Identification Fluency (NIF) ───────────────────────────────
    ('NIF', '1', 'BOY'): (33, 27, 16),
    
    # ── Next Number Fluency (NNF) ─────────────────────────────────────────
    ('NNF', '1', 'BOY'): (14, 12, 9),
    
    # ── Advanced Quantity Discrimination (AQD) ─────────────────────────────
    ('AQD', '1', 'BOY'): (13, 10, 6),
    ('AQD', '1', 'MOY'): (22, 19, 14),
    
    # ── Missing Number Fluency (MNF) ───────────────────────────────────────
    ('MNF', '1', 'BOY'): (6, 4, 2),
    ('MNF', '1', 'MOY'): (9, 8, 6),
    
    # ── Computation ────────────────────────────────────────────────────────
    ('Math_Computation', '1', 'BOY'): (6, 4, 2),
    ('Math_Computation', '1', 'MOY'): (14, 11, 7),
    ('Math_Computation', '2', 'BOY'): (8, 6, 0),
    ('Math_Computation', '2', 'MOY'): (14, 11, 0),
    ('Math_Computation', '2', 'EOY'): (14, 11, 0),
    ('Math_Computation', '3', 'BOY'): (12, 10, 0),
    ('Math_Computation', '3', 'MOY'): (16, 13, 0),
    ('Math_Computation', '3', 'EOY'): (18, 15, 0),
    ('Math_Computation', '4', 'BOY'): (14, 12, 0),
    ('Math_Computation', '4', 'MOY'): (18, 15, 0),
    ('Math_Computation', '4', 'EOY'): (20, 17, 0),
    
    # ── Concepts & Application ────────────────────────────────────────────
    ('Math_Concepts_Application', '2', 'BOY'): (18, 14, 0),
    ('Math_Concepts_Application', '2', 'MOY'): (31, 24, 0),
    ('Math_Concepts_Application', '2', 'EOY'): (31, 24, 0),
    ('Math_Concepts_Application', '3', 'BOY'): (25, 20, 0),
    ('Math_Concepts_Application', '3', 'MOY'): (38, 30, 0),
    ('Math_Concepts_Application', '3', 'EOY'): (42, 35, 0),
    ('Math_Concepts_Application', '4', 'BOY'): (30, 25, 0),
    ('Math_Concepts_Application', '4', 'MOY'): (45, 38, 0),
    ('Math_Concepts_Application', '4', 'EOY'): (50, 42, 0),
    
    # ── Math Composite (estimated for grades 3-4) ──────────────────────────
    ('Math_Composite', '3', 'BOY'): (28, 22, 0),
    ('Math_Composite', '3', 'MOY'): (42, 35, 0),
    ('Math_Composite', '3', 'EOY'): (48, 40, 0),
    ('Math_Composite', '4', 'BOY'): (32, 26, 0),
    ('Math_Composite', '4', 'MOY'): (48, 40, 0),
    ('Math_Composite', '4', 'EOY'): (55, 47, 0),
}

# All Acadience Math measure names supported
ACADIENCE_MATH_MEASURES = [
    'NIF', 'NNF', 'AQD', 'MNF', 'Math_Computation', 'Math_Concepts_Application', 'Math_Composite',
]

# Human-readable measure names
MATH_MEASURE_LABELS = {
    'NIF': 'Number Identification Fluency',
    'NNF': 'Next Number Fluency',
    'AQD': 'Advanced Quantity Discrimination',
    'MNF': 'Missing Number Fluency',
    'Math_Computation': 'Computation',
    'Computation': 'Computation',
    'Math_Concepts_Application': 'Concepts & Application',
    'Concepts_Application': 'Concepts & Application',
    'Concepts & Application': 'Concepts & Application',
    'Math_Composite': 'Math Composite Score',
}

# Measures applicable by grade
MATH_MEASURES_BY_GRADE = {
    'K': [],  # Kindergarten measures TBD
    '1': ['NIF', 'NNF', 'AQD', 'MNF', 'Math_Computation', 'Math_Composite'],
    '2': ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite'],
    '3': ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite'],
    '4': ['Math_Computation', 'Math_Concepts_Application', 'Math_Composite'],
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_math_benchmark_status(measure: str, grade, period, score: float) -> Optional[str]:
    """Return benchmark status for a given math score.
    
    Returns one of: 'Above Benchmark', 'At Benchmark',
    'Below Benchmark', 'Well Below Benchmark', or None if no
    benchmark data exists for the combination.
    """
    g = _g(grade)
    p = _p(period)
    if g is None or p is None or score is None:
        return None
    
    # Normalize measure name
    measure_map = {
        'Computation': 'Math_Computation',
        'Concepts & Application': 'Math_Concepts_Application',
        'Concepts_Application': 'Math_Concepts_Application',
    }
    measure = measure_map.get(measure, measure)
    
    key = (measure, g, p)
    if key not in _MATH_BENCHMARKS:
        return None
    
    above, goal, cut = _MATH_BENCHMARKS[key]
    if score >= above:
        return 'Above Benchmark'
    if score >= goal:
        return 'At Benchmark'
    if score >= cut:
        return 'Below Benchmark'
    return 'Well Below Benchmark'

def get_math_benchmark_thresholds(measure: str, grade, period) -> Optional[Dict[str, float]]:
    """Return benchmark thresholds for a math measure/grade/period.
    
    Returns dict with keys: above_benchmark, benchmark_goal, cut_point_risk
    or None if no data.
    """
    g = _g(grade)
    p = _p(period)
    if g is None or p is None:
        return None
    
    # Normalize measure name
    measure_map = {
        'Computation': 'Math_Computation',
        'Concepts & Application': 'Math_Concepts_Application',
        'Concepts_Application': 'Math_Concepts_Application',
    }
    measure = measure_map.get(measure, measure)
    
    key = (measure, g, p)
    if key not in _MATH_BENCHMARKS:
        return None
    
    above, goal, cut = _MATH_BENCHMARKS[key]
    return {
        'above_benchmark': above,
        'benchmark_goal': goal,
        'cut_point_risk': cut,
    }

def get_math_support_level(benchmark_status: Optional[str]) -> str:
    """Map benchmark status to instructional support level (tier).
    
    - At/Above Benchmark → Core (Tier 1)
    - Below Benchmark    → Strategic (Tier 2)
    - Well Below        → Intensive (Tier 3)
    """
    if benchmark_status in ('Above Benchmark', 'At Benchmark'):
        return 'Core (Tier 1)'
    elif benchmark_status == 'Below Benchmark':
        return 'Strategic (Tier 2)'
    elif benchmark_status == 'Well Below Benchmark':
        return 'Intensive (Tier 3)'
    return 'Unknown'

def math_benchmark_color(status: Optional[str]) -> str:
    """Return a hex color for a benchmark status."""
    return {
        'Above Benchmark': '#1a7431',
        'At Benchmark': '#28a745',
        'Below Benchmark': '#ffc107',
        'Well Below Benchmark': '#dc3545',
    }.get(status, '#6c757d')

def math_benchmark_emoji(status: Optional[str]) -> str:
    """Return an emoji for a benchmark status."""
    return {
        'Above Benchmark': '🟢',
        'At Benchmark': '🟢',
        'Below Benchmark': '🟡',
        'Well Below Benchmark': '🔴',
    }.get(status, '⚪')

# ── Approximate typical growth per period (BOY→MOY and MOY→EOY) ──────────
# Derived from published Acadience Math benchmark goals: typical growth ≈
# benchmark_goal(next_period) − benchmark_goal(current_period).
# Key: (measure, grade, from_period, to_period) → expected_typical_growth
_MATH_TYPICAL_GROWTH: Dict[Tuple[str, str, str, str], float] = {}


def _build_math_typical_growth():
    """Pre-compute typical math growth from benchmark goal deltas."""
    period_seq = ['BOY', 'MOY', 'EOY']
    for (measure, grade, period), (_, goal, _) in _MATH_BENCHMARKS.items():
        idx = period_seq.index(period) if period in period_seq else -1
        if idx < len(period_seq) - 1:
            next_period = period_seq[idx + 1]
            next_key = (measure, grade, next_period)
            if next_key in _MATH_BENCHMARKS:
                next_goal = _MATH_BENCHMARKS[next_key][1]
                _MATH_TYPICAL_GROWTH[(measure, grade, period, next_period)] = next_goal - goal


_build_math_typical_growth()


def get_math_typical_growth(measure: str, grade, from_period, to_period) -> Optional[float]:
    """Return the expected typical growth for a math measure between two periods."""
    g = _g(grade)
    fp = _p(from_period)
    tp = _p(to_period)
    if g is None or fp is None or tp is None:
        return None
    # Normalize measure name
    measure_map = {
        'Computation': 'Math_Computation',
        'Concepts & Application': 'Math_Concepts_Application',
        'Concepts_Application': 'Math_Concepts_Application',
    }
    measure = measure_map.get(measure, measure)
    return _MATH_TYPICAL_GROWTH.get((measure, g, fp, tp))


def classify_math_growth(measure: str, grade, from_period, to_period,
                         actual_growth: float) -> Optional[str]:
    """Classify math growth rate relative to typical peers.

    Returns one of:
      'Well Above Typical', 'Above Typical', 'Typical',
      'Below Typical', 'Well Below Typical', or None.
    """
    g = _g(grade)
    fp = _p(from_period)
    tp = _p(to_period)
    if g is None or fp is None or tp is None:
        return None
    # Normalize measure name
    measure_map = {
        'Computation': 'Math_Computation',
        'Concepts & Application': 'Math_Concepts_Application',
        'Concepts_Application': 'Math_Concepts_Application',
    }
    measure = measure_map.get(measure, measure)
    key = (measure, g, fp, tp)
    typical = _MATH_TYPICAL_GROWTH.get(key)
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


def math_growth_color(classification: Optional[str]) -> str:
    """Return a hex color for a math growth classification."""
    return {
        'Well Above Typical': '#1a7431',
        'Above Typical': '#28a745',
        'Typical': '#17a2b8',
        'Below Typical': '#ffc107',
        'Well Below Typical': '#dc3545',
    }.get(classification, '#6c757d')


def group_math_students(students_df: pd.DataFrame, scores_df: pd.DataFrame,
                       measure: str = 'Math_Composite') -> pd.DataFrame:
    """Group students into Core/Strategic/Intensive tiers based on math scores.
    
    Parameters
    ----------
    students_df : DataFrame with student_id, student_name, grade_level
    scores_df   : DataFrame with student_id, assessment_period, and a column
                  matching *measure* (e.g. 'Math_Composite' or 'overall_math_score')
    measure     : The Acadience Math measure to group by (or 'overall_math_score'
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
        score = latest.get(measure) if measure in latest.index else latest.get('overall_math_score')
        period = latest.get('assessment_period', 'EOY')
        
        # When score is the app's overall_math_score (0-100), use internal thresholds only.
        if measure not in latest.index and score is not None:
            # Internal 0-100 scale only
            if score >= 70:
                status = 'At Benchmark'
            elif score >= 50:
                status = 'Below Benchmark'
            else:
                status = 'Well Below Benchmark'
        else:
            status = get_math_benchmark_status(measure, grade, period, score)
            if status is None and score is not None:
                if score >= 70:
                    status = 'At Benchmark'
                elif score >= 50:
                    status = 'Below Benchmark'
                else:
                    status = 'Well Below Benchmark'
        
        support = get_math_support_level(status)
        
        # Identify weakest skill from component columns
        weakest = None
        component_cols = {
            'computation_component': 'Computation',
            'concepts_component': 'Concepts & Application',
            'number_fluency_component': 'Number Fluency',
            'quantity_discrimination_component': 'Quantity Discrimination',
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
