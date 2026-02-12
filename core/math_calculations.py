"""
Math score calculation algorithms
Similar structure to calculations.py for literacy
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

# Component weights for overall math score
# These weights can be adjusted based on teacher input
COMPONENT_WEIGHTS = {
    'computation': 0.40,
    'concepts': 0.30,
    'number_fluency': 0.20,
    'quantity_discrimination': 0.10,
}

# Risk level thresholds
RISK_THRESHOLD_HIGH = 50.0
RISK_THRESHOLD_MEDIUM = 70.0

# Trend calculation threshold (points)
TREND_THRESHOLD = 5.0

def normalize_math_score(value: any, max_value: float = None, grade_level: str = None, period: str = None) -> Optional[float]:
    """Normalize a math score to 0-100 scale.
    
    For math composite scores, normalization is grade/period specific
    since composite scores are not comparable across grades (per Acadience Math manual).
    """
    if pd.isna(value) or value == '' or value is None:
        return None
    
    try:
        # Handle string percentages
        if isinstance(value, str):
            value = value.replace('%', '').strip()
            if '/' in value:
                parts = value.split('/')
                if len(parts) == 2:
                    numerator = float(parts[0])
                    denominator = float(parts[1])
                    if denominator > 0:
                        return (numerator / denominator) * 100
            elif value.replace('.', '').isdigit():
                num_val = float(value)
                if num_val <= 1.0:
                    return num_val * 100
                elif max_value and num_val > max_value:
                    return min((num_val / max_value) * 100, 100)
                elif max_value and num_val <= max_value:
                    # Normalize even if <= max_value to get 0-100 scale
                    return min((num_val / max_value) * 100, 100)
                elif num_val <= 100:
                    return num_val
        
        # Handle numeric values
        num_val = float(value)
        
        # For composite scores, use grade/period-specific normalization
        # This is approximate - benchmark status is more reliable for comparison
        if max_value and num_val > max_value:
            return min((num_val / max_value) * 100, 100)
        elif max_value and num_val <= max_value:
            # Normalize even if <= max_value to get 0-100 scale
            return min((num_val / max_value) * 100, 100)
        elif num_val <= 100:
            return num_val
        else:
            # For raw composite scores that exceed 100, normalize based on typical max
            # Grade 1: max ~375, Grade 2: max ~125, etc.
            grade_maxes = {
                'Kindergarten': 200,
                'First': 400,
                'Second': 150,
                'Third': 150,
                'Fourth': 150,
            }
            if grade_level and grade_level in grade_maxes:
                return min((num_val / grade_maxes[grade_level]) * 100, 100)
            # Default normalization
            return min((num_val / 200) * 100, 100)
    except (ValueError, TypeError):
        return None

def calculate_math_component_scores(assessments: pd.DataFrame, period: str = None, grade_level: str = None) -> Dict[str, float]:
    """Calculate component scores from math assessments"""
    if period:
        assessments = assessments[assessments['assessment_period'] == period]
    
    components = {
        'computation': None,
        'concepts': None,
        'number_fluency': None,
        'quantity_discrimination': None,
    }
    
    # Computation component
    computation_assessments = assessments[
        assessments['assessment_type'].isin(['Math_Computation', 'Computation'])
    ]
    if not computation_assessments.empty:
        comp_scores = computation_assessments['score_normalized'].dropna()
        if not comp_scores.empty:
            components['computation'] = comp_scores.iloc[-1]  # Use most recent
    
    # Concepts & Application component
    concepts_assessments = assessments[
        assessments['assessment_type'].isin(['Math_Concepts_Application', 'Concepts_Application', 'Concepts & Application'])
    ]
    if not concepts_assessments.empty:
        concepts_scores = concepts_assessments['score_normalized'].dropna()
        if not concepts_scores.empty:
            components['concepts'] = concepts_scores.iloc[-1]
    
    # Number Fluency component (1st grade: NIF, NNF, MNF)
    number_fluency_types = ['NIF', 'NNF', 'MNF']
    number_fluency_assessments = assessments[
        assessments['assessment_type'].isin(number_fluency_types)
    ]
    if not number_fluency_assessments.empty:
        nf_scores = number_fluency_assessments['score_normalized'].dropna()
        if not nf_scores.empty:
            # Average of available number fluency measures
            components['number_fluency'] = nf_scores.mean()
    
    # Quantity Discrimination component (1st grade: AQD)
    aqd_assessments = assessments[assessments['assessment_type'] == 'AQD']
    if not aqd_assessments.empty:
        aqd_scores = aqd_assessments['score_normalized'].dropna()
        if not aqd_scores.empty:
            components['quantity_discrimination'] = aqd_scores.iloc[-1]
    
    return components

def calculate_overall_math_score(components: Dict[str, float], grade_level: str = None) -> Tuple[float, Dict[str, float]]:
    """Calculate overall math score from components.
    
    For 1st grade: uses all components
    For 2nd-4th grade: primarily computation and concepts
    """
    weighted_sum = 0.0
    total_weight = 0.0
    component_scores = {}
    
    # Adjust weights based on grade level
    if grade_level == 'First':
        # Use all components for 1st grade
        weights = COMPONENT_WEIGHTS
    else:
        # For 2nd-4th grade, focus on computation and concepts
        weights = {
            'computation': 0.50,
            'concepts': 0.50,
            'number_fluency': 0.0,
            'quantity_discrimination': 0.0,
        }
    
    for component, weight in weights.items():
        score = components.get(component)
        if score is not None and weight > 0:
            weighted_sum += score * weight
            total_weight += weight
            component_scores[component] = score
    
    if total_weight > 0:
        overall_score = weighted_sum / total_weight
    else:
        overall_score = None
    
    return overall_score, component_scores

def determine_math_risk_level(score: float) -> str:
    """Determine risk level from overall math score"""
    if score is None:
        return 'Unknown'
    elif score < RISK_THRESHOLD_HIGH:
        return 'High'
    elif score < RISK_THRESHOLD_MEDIUM:
        return 'Medium'
    else:
        return 'Low'

def calculate_math_trend(current_score: float, previous_score: float) -> str:
    """Calculate trend based on score change"""
    if current_score is None or previous_score is None:
        return 'Unknown'
    
    change = current_score - previous_score
    if change > TREND_THRESHOLD:
        return 'Improving'
    elif change < -TREND_THRESHOLD:
        return 'Declining'
    else:
        return 'Stable'

def process_math_assessment_score(assessment_type: str, score_value: str, grade_level: str = None, period: str = None) -> Optional[float]:
    """Process and normalize a math assessment score based on type"""
    if pd.isna(score_value) or score_value == '':
        return None
    
    # Math assessment types
    math_types = {
        'NIF': {'max': 60, 'label': 'Number Identification Fluency'},
        'NNF': {'max': 70, 'label': 'Next Number Fluency'},
        'AQD': {'max': 30, 'label': 'Advanced Quantity Discrimination'},
        'MNF': {'max': 15, 'label': 'Missing Number Fluency'},
        'Math_Computation': {'max': 20, 'label': 'Computation'},
        'Computation': {'max': 20, 'label': 'Computation'},
        'Math_Concepts_Application': {'max': 60, 'label': 'Concepts & Application'},
        'Concepts_Application': {'max': 60, 'label': 'Concepts & Application'},
        'Concepts & Application': {'max': 60, 'label': 'Concepts & Application'},
        'Math_Composite': {'max': None, 'label': 'Math Composite'},
    }
    
    if assessment_type in math_types:
        config = math_types[assessment_type]
        max_val = config['max']
        return normalize_math_score(score_value, max_value=max_val, grade_level=grade_level, period=period)
    
    # Generic normalization for unknown math types
    return normalize_math_score(score_value, grade_level=grade_level, period=period)
