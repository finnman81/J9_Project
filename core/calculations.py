"""
Literacy score calculation algorithms
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import re

# Reading level to numeric mapping (A-Z scale)
READING_LEVEL_MAP = {
    'AA': 10, 'A': 20, 'B': 30, 'C': 40, 'D': 50, 'E': 60, 'F': 70,
    'G': 75, 'H': 80, 'I': 85, 'J': 88, 'K': 90, 'L': 92, 'M': 94,
    'N': 95, 'O': 96, 'P': 97, 'Q': 98, 'R': 99, 'S': 100, 'T': 100
}

# Component weights for overall literacy score
COMPONENT_WEIGHTS = {
    'reading': 0.40,
    'benchmark': 0.30,
    'phonics_spelling': 0.20,
    'sight_words': 0.10
}

def normalize_reading_level(level: str) -> Optional[float]:
    """Convert reading level (A-Z) to numeric score (0-100)"""
    if pd.isna(level) or level == '' or level is None:
        return None
    
    level_str = str(level).strip().upper()
    
    # Handle ranges like "C/D", "P/Q"
    if '/' in level_str:
        parts = level_str.split('/')
        level_str = parts[0].strip()
    
    # Remove plus/minus
    level_str = re.sub(r'[+\-]', '', level_str)
    
    # Extract just letters
    level_str = re.sub(r'[^A-Z]', '', level_str)
    
    if level_str in READING_LEVEL_MAP:
        return float(READING_LEVEL_MAP[level_str])
    
    return None

def normalize_score(value: any, max_value: float = None) -> Optional[float]:
    """Normalize a score to 0-100 scale"""
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
                    return (num_val / max_value) * 100
                elif num_val <= 100:
                    return num_val
        
        # Handle numeric values
        num_val = float(value)
        if max_value and num_val > max_value:
            return (num_val / max_value) * 100
        elif num_val <= 100:
            return num_val
        else:
            return None
    except (ValueError, TypeError):
        return None

def calculate_component_scores(assessments: pd.DataFrame, period: str = None) -> Dict[str, float]:
    """Calculate component scores from assessments"""
    if period:
        assessments = assessments[assessments['assessment_period'] == period]
    
    components = {
        'reading': None,
        'benchmark': None,
        'phonics_spelling': None,
        'sight_words': None
    }
    
    # Reading level component
    reading_assessments = assessments[assessments['assessment_type'] == 'Reading_Level']
    if not reading_assessments.empty:
        reading_scores = reading_assessments['score_normalized'].dropna()
        if not reading_scores.empty:
            components['reading'] = reading_scores.iloc[-1]  # Use most recent
    
    # Benchmark component
    benchmark_assessments = assessments[
        assessments['assessment_type'].isin(['Benchmark', 'Easy_CBM'])
    ]
    if not benchmark_assessments.empty:
        benchmark_scores = benchmark_assessments['score_normalized'].dropna()
        if not benchmark_scores.empty:
            components['benchmark'] = benchmark_scores.mean()
    
    # Phonics/Spelling component
    phonics_spelling = assessments[
        assessments['assessment_type'].isin(['Phonics_Survey', 'Spelling', 'Spelling_Inventory'])
    ]
    if not phonics_spelling.empty:
        ps_scores = phonics_spelling['score_normalized'].dropna()
        if not ps_scores.empty:
            components['phonics_spelling'] = ps_scores.mean()
    
    # Sight words component
    sight_words = assessments[assessments['assessment_type'] == 'Sight_Words']
    if not sight_words.empty:
        sw_scores = sight_words['score_normalized'].dropna()
        if not sw_scores.empty:
            components['sight_words'] = sw_scores.mean()
    
    return components

def calculate_overall_literacy_score(components: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    """Calculate overall literacy score from components"""
    weighted_sum = 0.0
    total_weight = 0.0
    component_scores = {}
    
    for component, weight in COMPONENT_WEIGHTS.items():
        score = components.get(component)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight
            component_scores[component] = score
    
    if total_weight > 0:
        overall_score = weighted_sum / total_weight
    else:
        overall_score = None
    
    return overall_score, component_scores

def determine_risk_level(score: float) -> str:
    """Determine risk level from overall literacy score"""
    if score is None:
        return 'Unknown'
    elif score < 50:
        return 'High'
    elif score < 70:
        return 'Medium'
    else:
        return 'Low'

def calculate_trend(current_score: float, previous_score: float) -> str:
    """Calculate trend based on score change"""
    if current_score is None or previous_score is None:
        return 'Unknown'
    
    change = current_score - previous_score
    if change > 5:
        return 'Improving'
    elif change < -5:
        return 'Declining'
    else:
        return 'Stable'

def process_assessment_score(assessment_type: str, score_value: str) -> Optional[float]:
    """Process and normalize an assessment score based on type"""
    if pd.isna(score_value) or score_value == '':
        return None
    
    if assessment_type == 'Reading_Level':
        return normalize_reading_level(score_value)
    elif assessment_type == 'Sight_Words':
        # Assume max is 200 for sight words
        return normalize_score(score_value, max_value=200)
    elif assessment_type in ['Spelling', 'Spelling_Inventory']:
        # Handle fractions like "14/15" or percentages
        return normalize_score(score_value)
    elif assessment_type in ['Benchmark', 'Easy_CBM']:
        # Already should be 0-100 scale
        return normalize_score(score_value, max_value=100)
    elif assessment_type == 'Phonics_Survey':
        return normalize_score(score_value)
    else:
        # Generic normalization
        return normalize_score(score_value)
