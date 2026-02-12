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
    
    # ── Concepts & Application ────────────────────────────────────────────
    ('Math_Concepts_Application', '2', 'BOY'): (18, 14, 0),
    ('Math_Concepts_Application', '2', 'MOY'): (31, 24, 0),
    ('Math_Concepts_Application', '2', 'EOY'): (31, 24, 0),
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
