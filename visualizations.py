"""
Visualization functions for literacy assessment dashboard
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional

def create_risk_distribution_chart(df: pd.DataFrame, grade_filter: str = None) -> go.Figure:
    """Create pie chart showing risk level distribution"""
    if grade_filter and grade_filter != 'All':
        df = df[df['grade_level'] == grade_filter]
    
    risk_counts = df['risk_level'].value_counts()
    
    colors = {'High': '#dc3545', 'Medium': '#ffc107', 'Low': '#28a745', 'Unknown': '#6c757d'}
    
    fig = go.Figure(data=[go.Pie(
        labels=risk_counts.index,
        values=risk_counts.values,
        hole=0.4,
        marker_colors=[colors.get(label, '#6c757d') for label in risk_counts.index]
    )])
    
    fig.update_layout(
        title='Risk Level Distribution',
        showlegend=True,
        height=400
    )
    
    return fig

def create_grade_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """Create bar chart comparing average literacy scores by grade"""
    grade_avg = df.groupby('grade_level')['overall_literacy_score'].mean().reset_index()
    grade_avg.columns = ['grade_level', 'mean']
    grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth']
    grade_avg['grade_order'] = grade_avg['grade_level'].apply(
        lambda g: grade_order.index(g) if g in grade_order else len(grade_order)
    )
    grade_avg = grade_avg.sort_values('grade_order', ascending=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=grade_avg['grade_level'],
        y=grade_avg['mean'],
        marker_color='#5b9bd5',
        text=[f"{v:.0f}" for v in grade_avg['mean']],
        textposition='outside',
        name='Average Score'
    ))
    
    fig.update_layout(
        title='Average Score by Grade',
        xaxis_title='',
        yaxis_title='Average Score',
        height=400,
        yaxis=dict(range=[0, 105])
    )
    
    return fig

def create_score_trend_chart(df: pd.DataFrame, school_year: str = None) -> go.Figure:
    """Create line chart showing literacy score trends over time"""
    if school_year:
        df = df[df['school_year'] == school_year]
    
    period_order = ['Fall', 'Winter', 'Spring', 'EOY']
    df['assessment_period'] = pd.Categorical(df['assessment_period'], categories=period_order, ordered=True)
    
    trend_data = df.groupby('assessment_period')['overall_literacy_score'].mean().reset_index()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=trend_data['assessment_period'],
        y=trend_data['overall_literacy_score'],
        mode='lines+markers',
        name='Average Score',
        line=dict(color='#007bff', width=3),
        marker=dict(size=10)
    ))
    
    fig.update_layout(
        title='Schoolwide Literacy Score Trends',
        xaxis_title='Assessment Period',
        yaxis_title='Average Literacy Score',
        height=400,
        yaxis=dict(range=[0, 100])
    )
    
    return fig

def create_student_progress_chart(student_assessments: pd.DataFrame) -> go.Figure:
    """Create line chart showing individual student progress"""
    period_order = ['Fall', 'Winter', 'Spring', 'EOY']
    student_assessments['assessment_period'] = pd.Categorical(
        student_assessments['assessment_period'], 
        categories=period_order, 
        ordered=True
    )
    
    progress_data = student_assessments.sort_values('assessment_period')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=progress_data['assessment_period'],
        y=progress_data['overall_literacy_score'],
        mode='lines+markers',
        name='Literacy Score',
        line=dict(color='#007bff', width=3),
        marker=dict(size=12)
    ))
    
    # Add benchmark line at 70
    fig.add_hline(y=70, line_dash="dash", line_color="green", 
                  annotation_text="Benchmark (70)", annotation_position="right")
    
    fig.update_layout(
        title='Student Progress Over Time',
        xaxis_title='Assessment Period',
        yaxis_title='Literacy Score',
        height=400,
        yaxis=dict(range=[0, 100])
    )
    
    return fig

def create_reading_level_progression(student_assessments: pd.DataFrame) -> go.Figure:
    """Create step chart showing reading level progression"""
    reading_levels = student_assessments[
        student_assessments['assessment_type'] == 'Reading_Level'
    ].sort_values('assessment_period')
    
    if reading_levels.empty:
        return None
    
    # Map reading levels to numeric for visualization
    reading_map = {
        'AA': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'E': 6, 'F': 7,
        'G': 8, 'H': 9, 'I': 10, 'J': 11, 'K': 12, 'L': 13, 'M': 14,
        'N': 15, 'O': 16, 'P': 17, 'Q': 18, 'R': 19, 'S': 20, 'T': 21
    }
    
    reading_levels['level_numeric'] = reading_levels['score_value'].apply(
        lambda x: reading_map.get(str(x).strip().upper().split('/')[0].split('+')[0].split('-')[0], 0)
    )
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=reading_levels['assessment_period'],
        y=reading_levels['level_numeric'],
        mode='lines+markers',
        name='Reading Level',
        line=dict(color='#28a745', width=3, shape='hv'),  # Step chart
        marker=dict(size=12)
    ))
    
    fig.update_layout(
        title='Reading Level Progression',
        xaxis_title='Assessment Period',
        yaxis_title='Reading Level',
        height=400,
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(1, 22)),
            ticktext=list(reading_map.keys())[:21]
        )
    )
    
    return fig

def create_component_breakdown(current_components: dict, previous_components: dict = None) -> go.Figure:
    """Create radar chart showing component breakdown"""
    components = ['Reading', 'Benchmark', 'Phonics/Spelling', 'Sight Words']
    current_scores = [
        current_components.get('reading', 0) or 0,
        current_components.get('benchmark', 0) or 0,
        current_components.get('phonics_spelling', 0) or 0,
        current_components.get('sight_words', 0) or 0
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=current_scores,
        theta=components,
        fill='toself',
        name='Current Period',
        line_color='#007bff'
    ))
    
    if previous_components:
        previous_scores = [
            previous_components.get('reading', 0) or 0,
            previous_components.get('benchmark', 0) or 0,
            previous_components.get('phonics_spelling', 0) or 0,
            previous_components.get('sight_words', 0) or 0
        ]
        fig.add_trace(go.Scatterpolar(
            r=previous_scores,
            theta=components,
            fill='toself',
            name='Previous Period',
            line_color='#6c757d'
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        showlegend=True,
        title='Component Score Breakdown',
        height=400
    )
    
    return fig
