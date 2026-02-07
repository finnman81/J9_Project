"""
Student Detail Page
Deep dive into individual student progress
"""
import streamlit as st
import pandas as pd
from database import (
    get_all_students, get_db_connection, add_teacher_note, get_teacher_notes,
    upsert_student_goal, get_student_goals
)
from visualizations import (
    create_student_progress_chart,
    create_reading_level_progression,
    create_component_breakdown
)
from calculations import calculate_component_scores, calculate_overall_literacy_score, calculate_trend
from benchmarks import (
    get_benchmark_status, get_benchmark_thresholds, get_support_level,
    classify_growth, growth_color, benchmark_color, benchmark_emoji,
    compute_aimline, pm_trend_status, pm_status_color,
    generate_parent_report_html, ACADIENCE_MEASURES, MEASURE_LABELS,
    MEASURES_BY_GRADE, GRADE_ALIASES, PERIOD_MAP,
)
from erb_scoring import (
    ERB_SUBTESTS, ERB_SUBTEST_LABELS, ERB_SUBTEST_DESCRIPTIONS,
    summarize_erb_scores, classify_stanine, stanine_color, stanine_emoji,
    classify_percentile, percentile_color,
    classify_growth_percentile, growth_percentile_color,
    erb_stanine_to_tier, get_latest_erb_tier, blend_tiers,
)

def show_student_detail():
    st.title("👤 Student Detail")
    st.markdown("---")
    
    # Student selection by unique student_id to avoid name collisions
    students_df = get_all_students()

    if students_df.empty:
        st.warning("No students found in database. Please add students via Grade Entry page.")
        return

    selector_df = students_df[['student_id', 'student_name', 'grade_level', 'school_year', 'class_name']].copy()
    selector_df['student_label'] = selector_df.apply(
        lambda row: f"{row['student_name']} | {row['grade_level']} | {row['school_year']}" +
        (f" | {row['class_name']}" if pd.notna(row['class_name']) and row['class_name'] else ''),
        axis=1
    )
    selector_df = selector_df.sort_values(['student_name', 'school_year', 'grade_level'])

    selected_student_id = st.selectbox(
        "Select Student Record",
        selector_df['student_id'].tolist(),
        format_func=lambda sid: selector_df.loc[selector_df['student_id'] == sid, 'student_label'].iloc[0]
    )

    selected_student_row = students_df[students_df['student_id'] == selected_student_id].iloc[0]
    student_name = selected_student_row['student_name']

    # Get all records for this student across all grades/years (by name for multi-year view)
    student_records = students_df[students_df['student_name'] == student_name]
    
    # Student Info Card
    st.subheader("Student Information")
    
    # Show all grades/years this student has been tracked
    grade_years = student_records[['grade_level', 'school_year', 'class_name', 'teacher_name']].drop_duplicates()
    
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    
    with info_col1:
        st.metric("Student Name", student_name)
    with info_col2:
        grades_list = ', '.join(sorted(grade_years['grade_level'].unique()))
        st.metric("Grades Tracked", grades_list if grades_list else 'N/A')
    with info_col3:
        classes_list = ', '.join([c for c in grade_years['class_name'].dropna().unique() if c])
        st.metric("Classes", classes_list if classes_list else 'Not Assigned')
    with info_col4:
        teachers_list = ', '.join([t for t in grade_years['teacher_name'].dropna().unique() if t])
        st.metric("Teachers", teachers_list if teachers_list else 'Not Assigned')
    
    # Show grade/year breakdown
    if len(grade_years) > 1:
        st.info(f"📚 This student has been tracked across {len(grade_years)} grade/year combinations")
    
    st.markdown("---")
    
    # Grade Filter Section
    st.subheader("Filter by Grade")
    available_grades = sorted(grade_years['grade_level'].unique().tolist())
    selected_grades = st.multiselect(
        "Select Grades to Display",
        available_grades,
        default=available_grades,  # Show all by default
        help="Select which grades to include in charts and analysis"
    )
    
    if not selected_grades:
        st.warning("Please select at least one grade to display.")
        return
    
    st.markdown("---")
    
    # Get all literacy scores for this student (across all grades/years)
    conn = get_db_connection()
    all_scores_query = '''
        SELECT
            ls.score_id,
            ls.student_id,
            ls.school_year AS score_school_year,
            ls.assessment_period,
            ls.overall_literacy_score,
            ls.reading_component,
            ls.phonics_component,
            ls.spelling_component,
            ls.sight_words_component,
            ls.risk_level,
            ls.trend,
            ls.calculated_at,
            s.grade_level,
            s.school_year,
            s.class_name
        FROM literacy_scores ls
        JOIN students s ON ls.student_id = s.student_id
        WHERE s.student_name = %s
        ORDER BY
            s.school_year,
            s.grade_level,
            CASE ls.assessment_period
                WHEN 'Fall' THEN 1
                WHEN 'Winter' THEN 2
                WHEN 'Spring' THEN 3
                WHEN 'EOY' THEN 4
                ELSE 0
            END,
            ls.calculated_at
    '''
    all_scores_df = pd.read_sql_query(all_scores_query, conn, params=[student_name])
    conn.close()
    
    # Clean DataFrame: drop duplicates and reset index
    if not all_scores_df.empty:
        # Drop duplicate rows if any
        all_scores_df = all_scores_df.drop_duplicates().reset_index(drop=True)
        # Filter by selected grades
        all_scores_df = all_scores_df[all_scores_df['grade_level'].isin(selected_grades)].reset_index(drop=True)
    
    # Get latest score (most recent period by chronological order)
    latest_score = None
    if not all_scores_df.empty:
        period_key = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        latest_df = all_scores_df.copy()
        latest_df['year_key'] = latest_df['school_year'].apply(lambda val: int(str(val).split('-')[0]) if str(val).split('-')[0].isdigit() else 0)
        latest_df['period_key'] = latest_df['assessment_period'].map(period_key).fillna(0)
        latest_df = latest_df.sort_values(['year_key', 'period_key', 'calculated_at'])
        latest_score = latest_df.iloc[-1].to_dict()

    # Trend override: if trend is Unknown, compute using previous period in same grade/year
    if latest_score and latest_score.get('trend') == 'Unknown' and not all_scores_df.empty:
        current_grade = latest_score.get('grade_level')
        current_year = latest_score.get('school_year')
        current_period = latest_score.get('assessment_period')
        current_score = latest_score.get('overall_literacy_score')

        period_order = ['Fall', 'Winter', 'Spring', 'EOY']
        if current_period in period_order:
            current_index = period_order.index(current_period)
            if current_index > 0:
                prev_period = period_order[current_index - 1]
                prev_row = all_scores_df[
                    (all_scores_df['grade_level'] == current_grade) &
                    (all_scores_df['school_year'] == current_year) &
                    (all_scores_df['assessment_period'] == prev_period)
                ]
                if not prev_row.empty:
                    prev_score = prev_row.iloc[-1].get('overall_literacy_score')
                    if current_score is not None and prev_score is not None:
                        latest_score['trend'] = calculate_trend(current_score, prev_score)

    # Fallback trend: compare last two available scores across years/grades
    if latest_score and latest_score.get('trend') == 'Unknown' and not all_scores_df.empty:
        scores_with_values = all_scores_df[all_scores_df['overall_literacy_score'].notna()].copy()
        if len(scores_with_values) >= 2:
            # Order by school year, grade, period
            period_key = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
            grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth']

            def school_year_key(val):
                try:
                    return int(str(val).split('-')[0])
                except Exception:
                    return 0

            scores_with_values['year_key'] = scores_with_values['school_year'].apply(school_year_key)
            scores_with_values['period_key'] = scores_with_values['assessment_period'].map(period_key).fillna(0)
            scores_with_values['grade_key'] = scores_with_values['grade_level'].apply(
                lambda g: grade_order.index(g) if g in grade_order else len(grade_order)
            )

            scores_with_values = scores_with_values.sort_values(
                ['year_key', 'grade_key', 'period_key', 'calculated_at']
            )

            last_two = scores_with_values.tail(2)
            if len(last_two) == 2:
                prev_score = last_two.iloc[0]['overall_literacy_score']
                current_score = last_two.iloc[1]['overall_literacy_score']
                if prev_score is not None and current_score is not None:
                    latest_score['trend'] = calculate_trend(current_score, prev_score)
    
    # Class Comparison Section
    if not student_records.empty:
        # Get class name from most recent record
        latest_record = student_records.iloc[-1]
        class_name = latest_record.get('class_name')
        
        if class_name and pd.notna(class_name):
            st.subheader("Class Comparison")
            
            # Get class average for comparison
            conn = get_db_connection()
            class_comparison_query = '''
                SELECT 
                    AVG(ls.overall_literacy_score) as class_avg,
                    COUNT(DISTINCT s.student_id) as class_size
                FROM literacy_scores ls
                JOIN students s ON ls.student_id = s.student_id
                WHERE s.class_name = %s AND s.school_year = %s
                AND ls.assessment_period = (
                    SELECT assessment_period 
                    FROM literacy_scores 
                    WHERE student_id = s.student_id
                    ORDER BY calculated_at DESC
                    LIMIT 1
                )
            '''
            class_stats = pd.read_sql_query(
                class_comparison_query, 
                conn, 
                params=[class_name, latest_record['school_year']]
            )
            conn.close()
            
            if not class_stats.empty and class_stats.iloc[0]['class_avg'] is not None:
                class_avg = class_stats.iloc[0]['class_avg']
                class_size = class_stats.iloc[0]['class_size']
                student_current_score = latest_score.get('overall_literacy_score', 0) if latest_score else 0
                
                comp_col1, comp_col2, comp_col3 = st.columns(3)
                with comp_col1:
                    st.metric("Class Average", f"{class_avg:.1f}")
                with comp_col2:
                    st.metric("Student Score", f"{student_current_score:.1f}")
                with comp_col3:
                    difference = student_current_score - class_avg
                    st.metric("Difference", f"{difference:+.1f}", delta=f"{difference:+.1f} vs class")
                
                # Visual comparison chart
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=['Class Average', 'Student'],
                    y=[class_avg, student_current_score],
                    marker_color=['#6c757d', '#007bff'],
                    text=[f"{class_avg:.1f}", f"{student_current_score:.1f}"],
                    textposition='auto'
                ))
                fig.update_layout(
                    title=f'Student vs Class Average ({class_name})',
                    yaxis_title='Literacy Score',
                    height=300,
                    yaxis=dict(range=[0, 100])
                )
                st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Current Status KPIs
    st.subheader("Current Status")
    
    # Initialize variables so they're available for timeline/export even without scores
    interventions_df = pd.DataFrame()
    bm_status = None

    status_col1, status_col2, status_col3, status_col4, status_col5 = st.columns(5)
    
    if latest_score:
        overall_score = latest_score.get('overall_literacy_score', 0)
        risk_level = latest_score.get('risk_level', 'Unknown')
        trend = latest_score.get('trend', 'Unknown')
        period = latest_score.get('assessment_period', 'N/A')
        
        with status_col1:
            st.metric("Literacy Score", f"{overall_score:.1f}" if overall_score else "N/A")
        
        with status_col2:
            risk_color = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}.get(risk_level, '⚪')
            st.metric("Risk Level", f"{risk_color} {risk_level}")
        
        with status_col3:
            trend_icon = {'Improving': '📈', 'Declining': '📉', 'Stable': '➡️'}.get(trend, '❓')
            st.metric("Trend", f"{trend_icon} {trend}")
        
        with status_col4:
            # Acadience-aligned benchmark status using internal score thresholds
            current_grade = latest_score.get('grade_level', '')
            current_period = latest_score.get('assessment_period', '')
            bm_status = get_benchmark_status('Composite', current_grade, current_period, overall_score)
            if bm_status is None:
                # Fallback to internal thresholds
                if overall_score >= 70:
                    bm_status = 'At Benchmark'
                elif overall_score >= 50:
                    bm_status = 'Below Benchmark'
                else:
                    bm_status = 'Well Below Benchmark'
            bm_icon = benchmark_emoji(bm_status)
            st.metric("Benchmark Status", f"{bm_icon} {bm_status}")
            support_level = get_support_level(bm_status)
            st.caption(f"Support: {support_level}")
        
        # Get active interventions (using student_name query)
        conn = get_db_connection()
        interventions_query = '''
            SELECT i.*, s.student_name, s.grade_level, s.school_year
            FROM interventions i
            JOIN students s ON i.student_id = s.student_id
            WHERE s.student_name = %s
            ORDER BY i.start_date DESC
        '''
        interventions_df = pd.read_sql_query(interventions_query, conn, params=[student_name])
        conn.close()
        
        # Clean DataFrame: drop duplicates and reset index
        if not interventions_df.empty:
            # Drop duplicate rows if any
            interventions_df = interventions_df.drop_duplicates().reset_index(drop=True)
            # Filter interventions by selected grades
            interventions_df = interventions_df[interventions_df['grade_level'].isin(selected_grades)].reset_index(drop=True)
        
        active_interventions = interventions_df[interventions_df['status'] == 'Active'].reset_index(drop=True) if not interventions_df.empty else pd.DataFrame()
        
        with status_col5:
            st.metric("Active Interventions", len(active_interventions))
    else:
        st.info("No literacy score data available for this student.")
    
    st.markdown("---")
    
    # Progress Visualizations
    st.subheader("Progress Visualizations & Graphs")
    
    # Get all assessments for this student (across all grades/years)
    conn = get_db_connection()
    all_assessments_query = '''
        SELECT
            a.assessment_id,
            a.student_id,
            a.assessment_type,
            a.assessment_period,
            a.score_value,
            a.score_normalized,
            a.assessment_date,
            a.notes,
            a.concerns,
            s.grade_level,
            s.school_year,
            s.class_name
        FROM assessments a
        JOIN students s ON a.student_id = s.student_id
        WHERE s.student_name = %s
        ORDER BY s.school_year, s.grade_level, a.assessment_date DESC,
            CASE a.assessment_period
                WHEN 'Fall' THEN 1
                WHEN 'Winter' THEN 2
                WHEN 'Spring' THEN 3
                WHEN 'EOY' THEN 4
                ELSE 0
            END
    '''
    assessments_df = pd.read_sql_query(all_assessments_query, conn, params=[student_name])
    conn.close()
    
    # Clean DataFrame: drop duplicates and reset index
    if not assessments_df.empty:
        # Drop duplicate rows if any
        assessments_df = assessments_df.drop_duplicates().reset_index(drop=True)
        # Filter assessments by selected grades
        assessments_df = assessments_df[assessments_df['grade_level'].isin(selected_grades)].reset_index(drop=True)
    
    if not all_scores_df.empty:
        # Create comprehensive progress chart showing all years
        scores_df = all_scores_df.copy()
        
        # Create a combined period label (grade + period)
        scores_df['period_label'] = scores_df['grade_level'] + ' - ' + scores_df['assessment_period']
        
        if not scores_df.empty:
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                # Enhanced progress chart with aimline and benchmark zones
                import plotly.graph_objects as go

                fig = go.Figure()

                # Add benchmark zone shading (green/yellow/red)
                fig.add_hrect(y0=70, y1=100, fillcolor="#28a745", opacity=0.07,
                              line_width=0, annotation_text="At/Above Benchmark",
                              annotation_position="top right")
                fig.add_hrect(y0=50, y1=70, fillcolor="#ffc107", opacity=0.07,
                              line_width=0, annotation_text="Below Benchmark",
                              annotation_position="top right")
                fig.add_hrect(y0=0, y1=50, fillcolor="#dc3545", opacity=0.07,
                              line_width=0, annotation_text="Well Below",
                              annotation_position="top right")

                # Actual scores
                fig.add_trace(go.Scatter(
                    x=scores_df['period_label'],
                    y=scores_df['overall_literacy_score'],
                    mode='lines+markers',
                    name='Literacy Score',
                    line=dict(color='#007bff', width=3),
                    marker=dict(size=12)
                ))

                # Add aimline if student has a goal
                goal_frames = []
                if not student_records.empty:
                    for sid in student_records['student_id'].tolist():
                        gf = get_student_goals(sid)
                        if not gf.empty:
                            goal_frames.append(gf)
                if goal_frames:
                    all_goals = pd.concat(goal_frames, ignore_index=True)
                    lit_goals = all_goals[all_goals['measure'] == 'overall_literacy_score']
                    if not lit_goals.empty:
                        goal_row = lit_goals.iloc[0]
                        base = goal_row['baseline_score']
                        tgt = goal_row['target_score']
                        n_pts = len(scores_df)
                        if n_pts >= 2 and base is not None and tgt is not None:
                            aimline_vals = compute_aimline(base, tgt, 0, n_pts - 1, n_pts)
                            fig.add_trace(go.Scatter(
                                x=scores_df['period_label'],
                                y=aimline_vals,
                                mode='lines',
                                name='Aimline (Goal)',
                                line=dict(color='#6c757d', width=2, dash='dash')
                            ))
                            # Evaluate PM trend status
                            actual_scores = scores_df['overall_literacy_score'].dropna().tolist()
                            trend_status = pm_trend_status(actual_scores, aimline_vals)
                            trend_color = pm_status_color(trend_status)
                            fig.add_annotation(
                                x=scores_df['period_label'].iloc[-1],
                                y=max(actual_scores[-1] if actual_scores else 0, tgt),
                                text=f"PM Status: {trend_status}",
                                showarrow=True, arrowhead=2,
                                font=dict(color=trend_color, size=12),
                                bgcolor='white', bordercolor=trend_color,
                            )

                fig.update_layout(
                    title='Student Progress with Benchmark Zones',
                    xaxis_title='Grade - Assessment Period',
                    yaxis_title='Literacy Score',
                    height=400,
                    yaxis=dict(range=[0, 100]),
                    xaxis=dict(tickangle=45)
                )

                st.plotly_chart(fig, use_container_width=True)
            
            with chart_col2:
                reading_chart = create_reading_level_progression(assessments_df)
                if reading_chart:
                    st.plotly_chart(reading_chart, use_container_width=True)
                else:
                    st.info("No reading level data available")
            
            # Additional Graphs Section
            st.markdown("### Additional Analytics")
            
            graph_col1, graph_col2 = st.columns(2)
            
            with graph_col1:
                # Risk Level Over Time
                if len(scores_df) > 1:
                    risk_over_time = scores_df.copy()
                    
                    risk_map = {'High': 3, 'Medium': 2, 'Low': 1, 'Unknown': 0}
                    risk_over_time['risk_numeric'] = risk_over_time['risk_level'].map(risk_map)
                    
                    import plotly.graph_objects as go
                    fig_risk = go.Figure()
                    fig_risk.add_trace(go.Scatter(
                        x=risk_over_time['period_label'],
                        y=risk_over_time['risk_numeric'],
                        mode='lines+markers',
                        name='Risk Level',
                        line=dict(color='#dc3545', width=3),
                        marker=dict(size=12),
                        text=risk_over_time['risk_level'],
                        textposition='top center'
                    ))
                    fig_risk.update_layout(
                        title='Risk Level Over Time',
                        xaxis_title='Grade - Assessment Period',
                        yaxis_title='Risk Level',
                        height=350,
                        yaxis=dict(
                            tickmode='array',
                            tickvals=[0, 1, 2, 3],
                            ticktext=['Unknown', 'Low', 'Medium', 'High'],
                            range=[-0.5, 3.5]
                        ),
                        xaxis=dict(tickangle=45)
                    )
                    st.plotly_chart(fig_risk, use_container_width=True)
            
            with graph_col2:
                # Component Scores Over Time
                if len(scores_df) > 1:
                    components_over_time = scores_df.copy()
                    
                    fig_components = go.Figure()
                    
                    # Add each component as a line
                    if components_over_time['reading_component'].notna().any():
                        fig_components.add_trace(go.Scatter(
                            x=components_over_time['period_label'],
                            y=components_over_time['reading_component'],
                            mode='lines+markers',
                            name='Reading',
                            line=dict(color='#007bff', width=2)
                        ))
                    
                    if components_over_time['phonics_component'].notna().any():
                        fig_components.add_trace(go.Scatter(
                            x=components_over_time['period_label'],
                            y=components_over_time['phonics_component'],
                            mode='lines+markers',
                            name='Phonics/Spelling',
                            line=dict(color='#28a745', width=2)
                        ))
                    
                    if components_over_time['sight_words_component'].notna().any():
                        fig_components.add_trace(go.Scatter(
                            x=components_over_time['period_label'],
                            y=components_over_time['sight_words_component'],
                            mode='lines+markers',
                            name='Sight Words',
                            line=dict(color='#ffc107', width=2)
                        ))
                    
                    fig_components.update_layout(
                        title='Component Scores Over Time',
                        xaxis_title='Grade - Assessment Period',
                        yaxis_title='Score',
                        height=350,
                        yaxis=dict(range=[0, 100]),
                        xaxis=dict(tickangle=45),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_components, use_container_width=True)
            
            # Grade Comparison Chart
            if len(selected_grades) > 1:
                st.markdown("### Performance by Grade")
                grade_avg_scores = scores_df.groupby('grade_level')['overall_literacy_score'].agg(['mean', 'std']).reset_index()
                grade_avg_scores = grade_avg_scores.sort_values('mean', ascending=False)
                
                fig_grade = go.Figure()
                fig_grade.add_trace(go.Bar(
                    x=grade_avg_scores['grade_level'],
                    y=grade_avg_scores['mean'],
                    error_y=dict(type='data', array=grade_avg_scores['std']),
                    marker_color='#17a2b8',
                    text=[f"{x:.1f}" for x in grade_avg_scores['mean']],
                    textposition='auto',
                    name='Average Score'
                ))
                fig_grade.update_layout(
                    title='Average Literacy Score by Grade',
                    xaxis_title='Grade Level',
                    yaxis_title='Average Literacy Score',
                    height=350,
                    yaxis=dict(range=[0, 100])
                )
                st.plotly_chart(fig_grade, use_container_width=True)
            
            # Component breakdown
            if latest_score and not assessments_df.empty:
                current_period = latest_score.get('assessment_period')
                current_grade = latest_score.get('grade_level')
                current_year = latest_score.get('school_year')
                
                # Ensure assessments_df has clean index before filtering
                # Use .loc with boolean indexing to avoid reindex issues
                if not assessments_df.empty:
                    assessments_clean = assessments_df.copy()
                    # Get assessments for latest period using .loc
                    mask = (
                        (assessments_clean['assessment_period'] == current_period) &
                        (assessments_clean['grade_level'] == current_grade) &
                        (assessments_clean['school_year'] == current_year)
                    )
                    period_assessments = assessments_clean.loc[mask].reset_index(drop=True)
                else:
                    period_assessments = pd.DataFrame()
                current_components_dict = calculate_component_scores(period_assessments, current_period)
                
                # Get previous period for comparison (same grade/year)
                previous_period = None
                if current_period == 'Winter':
                    previous_period = 'Fall'
                elif current_period == 'Spring':
                    previous_period = 'Winter'
                elif current_period == 'EOY':
                    previous_period = 'Spring'
                
                previous_components_dict = None
                if previous_period and not assessments_df.empty:
                    prev_mask = (
                        (assessments_clean['assessment_period'] == previous_period) &
                        (assessments_clean['grade_level'] == current_grade) &
                        (assessments_clean['school_year'] == current_year)
                    )
                    prev_period_assessments = assessments_clean.loc[prev_mask].reset_index(drop=True)
                    if not prev_period_assessments.empty:
                        previous_components_dict = calculate_component_scores(prev_period_assessments, previous_period)
                
                component_chart = create_component_breakdown(current_components_dict, previous_components_dict)
                st.plotly_chart(component_chart, use_container_width=True)
        else:
            st.info("No literacy score history available for visualization.")
    else:
        st.info("No assessment data available for this student.")
    
    # Enhancement: Unified timeline, notes, goals, and export summaries
    st.subheader("Timeline View")
    timeline_rows = []
    if not assessments_df.empty:
        for _, r in assessments_df.iterrows():
            timeline_rows.append({'date': r.get('assessment_date'), 'event': f"Assessment: {r.get('assessment_type')} ({r.get('assessment_period')})", 'details': f"Score={r.get('score_normalized')}"})
    if not interventions_df.empty:
        for _, r in interventions_df.iterrows():
            timeline_rows.append({'date': r.get('start_date'), 'event': f"Intervention Start: {r.get('intervention_type')}", 'details': r.get('status')})
            if pd.notna(r.get('end_date')):
                timeline_rows.append({'date': r.get('end_date'), 'event': f"Intervention End: {r.get('intervention_type')}", 'details': r.get('status')})
    if student_records is not None and not student_records.empty:
        note_frames = [get_teacher_notes(sid) for sid in student_records['student_id'].tolist()]
        note_frames = [n for n in note_frames if not n.empty]
        if note_frames:
            all_notes = pd.concat(note_frames, ignore_index=True)
            for _, r in all_notes.iterrows():
                timeline_rows.append({'date': r.get('note_date') or r.get('created_at'), 'event': f"Note ({r.get('tag') or 'General'})", 'details': r.get('note_text')})
        else:
            all_notes = pd.DataFrame()
    else:
        all_notes = pd.DataFrame()

    if timeline_rows:
        timeline_df = pd.DataFrame(timeline_rows)
        timeline_df['date'] = pd.to_datetime(timeline_df['date'], errors='coerce')
        timeline_df = timeline_df.sort_values('date', ascending=False)
        st.dataframe(timeline_df, use_container_width=True, height=240)
    else:
        st.info("No timeline events available.")

    st.subheader("Teacher Notes")
    ncol1, ncol2, ncol3 = st.columns([1,1,2])
    with ncol1:
        note_tag = st.selectbox('Tag', ['Attendance','Behavior','Comprehension','Decoding','Home Reading','Other'])
    with ncol2:
        note_date = st.date_input('Note Date')
    with ncol3:
        note_text = st.text_input('Add Teacher Note')
    if st.button('Save Note') and note_text.strip() and selected_student_id:
        add_teacher_note(selected_student_id, note_text.strip(), note_tag, note_date.strftime('%Y-%m-%d'))
        st.success('Teacher note saved.')
        st.rerun()
    if 'all_notes' in locals() and not all_notes.empty:
        st.dataframe(all_notes[['note_date','tag','note_text','created_by']], use_container_width=True, height=160)

    st.subheader("Goal Tracking")
    gcol1, gcol2, gcol3, gcol4 = st.columns(4)
    with gcol1:
        goal_measure = st.selectbox('Measure', ['overall_literacy_score','reading_component','phonics_component','sight_words_component'])
    with gcol2:
        baseline = st.number_input('Baseline', min_value=0.0, max_value=100.0, step=0.1)
    with gcol3:
        target = st.number_input('Target', min_value=0.0, max_value=100.0, step=0.1, value=70.0)
    with gcol4:
        expected_growth = st.number_input('Expected Weekly Growth', min_value=0.0, step=0.1, value=0.8)
    gd1, gd2 = st.columns(2)
    with gd1:
        goal_start = st.date_input('Goal Start')
    with gd2:
        goal_target = st.date_input('Goal Target Date')
    if st.button('Save Goal') and selected_student_id:
        upsert_student_goal(selected_student_id, goal_measure, baseline, target, expected_growth, goal_start.strftime('%Y-%m-%d'), goal_target.strftime('%Y-%m-%d'))
        st.success('Goal saved.')
        st.rerun()

    if not student_records.empty:
        goal_frames = [get_student_goals(sid) for sid in student_records['student_id'].tolist()]
        goal_frames = [g for g in goal_frames if not g.empty]
        if goal_frames:
            goals_df = pd.concat(goal_frames, ignore_index=True)
            latest_val = latest_score.get(goal_measure) if latest_score and goal_measure in latest_score else None
            goals_df['actual_growth'] = (latest_val - goals_df['baseline_score']) if latest_val is not None else None
            st.dataframe(goals_df[['measure','baseline_score','target_score','expected_weekly_growth','actual_growth','start_date','target_date']], use_container_width=True, height=180)

    # ── Growth Rate Classification (Pathways of Progress lite) ──────────
    st.subheader("Growth Rate Analysis")
    if not all_scores_df.empty and len(all_scores_df) >= 2:
        period_order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        growth_rows = []
        for grade_val in all_scores_df['grade_level'].unique():
            grade_scores = all_scores_df[all_scores_df['grade_level'] == grade_val].copy()
            grade_scores['p_order'] = grade_scores['assessment_period'].map(period_order).fillna(0)
            grade_scores = grade_scores.sort_values('p_order')
            for i in range(1, len(grade_scores)):
                prev = grade_scores.iloc[i - 1]
                curr = grade_scores.iloc[i]
                prev_score = prev.get('overall_literacy_score')
                curr_score = curr.get('overall_literacy_score')
                if prev_score is not None and curr_score is not None and pd.notna(prev_score) and pd.notna(curr_score):
                    actual_growth = curr_score - prev_score
                    classification = classify_growth(
                        'Composite', grade_val,
                        prev['assessment_period'], curr['assessment_period'],
                        actual_growth
                    )
                    growth_rows.append({
                        'Grade': grade_val,
                        'From': prev['assessment_period'],
                        'To': curr['assessment_period'],
                        'Start Score': f"{prev_score:.1f}",
                        'End Score': f"{curr_score:.1f}",
                        'Growth': f"{actual_growth:+.1f}",
                        'Growth Rate': classification or 'N/A',
                    })
        if growth_rows:
            growth_df = pd.DataFrame(growth_rows)
            def color_growth(val):
                colors = {
                    'Well Above Typical': 'background-color: #d4edda; color: #155724',
                    'Above Typical': 'background-color: #d4edda; color: #155724',
                    'Typical': 'background-color: #d1ecf1; color: #0c5460',
                    'Below Typical': 'background-color: #fff3cd; color: #856404',
                    'Well Below Typical': 'background-color: #f8d7da; color: #721c24',
                }
                return colors.get(val, '')
            styled = growth_df.style.map(color_growth, subset=['Growth Rate'])
            st.dataframe(styled, use_container_width=True, height=200)
        else:
            st.info("Not enough data points to calculate growth rates.")
    else:
        st.info("At least two assessment periods needed for growth analysis.")

    # ── ERB / CTP5 Scores ──────────────────────────────────────────────
    erb_summaries = []
    if not assessments_df.empty:
        erb_summaries = summarize_erb_scores(assessments_df, student_name)

    if erb_summaries:
        st.subheader("ERB / CTP5 Assessment Scores")
        st.caption("Norm-referenced scores from the Comprehensive Testing Program (CTP5) by ERB.")

        # Latest ERB scores per subtest
        import plotly.graph_objects as go

        # Group by subtest, take latest entry per subtest
        erb_latest = {}
        for s in erb_summaries:
            key = s['subtest']
            if key not in erb_latest:
                erb_latest[key] = s
            else:
                # Keep the one from the later period/year
                erb_latest[key] = s  # already sorted by query order (latest last)

        # ── Stanine bar chart ─────────────────────────────
        erb_chart_col1, erb_chart_col2 = st.columns(2)
        with erb_chart_col1:
            labels = [erb_latest[k]['label'] for k in erb_latest]
            stanines = [erb_latest[k]['stanine'] or 0 for k in erb_latest]
            bar_colors = [stanine_color(s) for s in stanines]

            fig_stanine = go.Figure()
            fig_stanine.add_trace(go.Bar(
                x=labels, y=stanines,
                marker_color=bar_colors,
                text=[f"{s}" for s in stanines],
                textposition='auto',
            ))
            # Add band lines
            fig_stanine.add_hrect(y0=0, y1=3.5, fillcolor="#dc3545", opacity=0.06, line_width=0)
            fig_stanine.add_hrect(y0=3.5, y1=6.5, fillcolor="#ffc107", opacity=0.06, line_width=0)
            fig_stanine.add_hrect(y0=6.5, y1=9.5, fillcolor="#28a745", opacity=0.06, line_width=0)
            fig_stanine.update_layout(
                title='ERB Stanine Scores by Subtest',
                yaxis_title='Stanine', yaxis=dict(range=[0, 9.5], dtick=1),
                xaxis_title='', height=350, xaxis=dict(tickangle=30),
            )
            st.plotly_chart(fig_stanine, use_container_width=True)

        # ── Percentile display ────────────────────────────
        with erb_chart_col2:
            percentiles = [erb_latest[k].get('percentile') or 0 for k in erb_latest]
            pct_colors = [percentile_color(p) for p in percentiles]

            fig_pct = go.Figure()
            fig_pct.add_trace(go.Bar(
                x=labels, y=percentiles,
                marker_color=pct_colors,
                text=[f"{int(p)}th" for p in percentiles],
                textposition='auto',
            ))
            fig_pct.add_hline(y=50, line_dash="dash", line_color="#6c757d",
                              annotation_text="50th Percentile", annotation_position="right")
            fig_pct.update_layout(
                title='ERB Percentile Ranks by Subtest',
                yaxis_title='Percentile', yaxis=dict(range=[0, 100]),
                xaxis_title='', height=350, xaxis=dict(tickangle=30),
            )
            st.plotly_chart(fig_pct, use_container_width=True)

        # ── Detail table ──────────────────────────────────
        erb_table_rows = []
        for s in erb_summaries:
            icon = stanine_emoji(s['stanine'])
            growth_class = classify_growth_percentile(s['growth_percentile']) if s['growth_percentile'] else 'N/A'
            erb_table_rows.append({
                'Subtest': s['label'],
                'Period': s['period'],
                'Year': s.get('school_year', ''),
                'Stanine': f"{icon} {s['stanine']}" if s['stanine'] else 'N/A',
                'Percentile': f"{int(s['percentile'])}th" if s['percentile'] else 'N/A',
                'Scale Score': int(s['scale_score']) if s['scale_score'] else 'N/A',
                'Growth %ile': f"{int(s['growth_percentile'])}" if s['growth_percentile'] else 'N/A',
                'Growth Status': growth_class,
                'Tier': s['tier'],
            })
        erb_table_df = pd.DataFrame(erb_table_rows)

        def color_erb_tier(val):
            if 'Core' in str(val):
                return 'background-color: #d4edda; color: #155724'
            elif 'Strategic' in str(val):
                return 'background-color: #fff3cd; color: #856404'
            elif 'Intensive' in str(val):
                return 'background-color: #f8d7da; color: #721c24'
            return ''

        styled_erb = erb_table_df.style.map(color_erb_tier, subset=['Tier'])
        st.dataframe(styled_erb, use_container_width=True, height=250)

        # ── Growth percentile tracking across years ───────
        growth_data = [s for s in erb_summaries if s.get('growth_percentile')]
        if growth_data:
            st.markdown("#### Growth Percentile Tracking")
            growth_chart_data = {}
            for s in growth_data:
                subtest = s['label']
                if subtest not in growth_chart_data:
                    growth_chart_data[subtest] = {'periods': [], 'values': []}
                period_label = f"{s.get('grade_level', '')} {s['period']} {s.get('school_year', '')}"
                growth_chart_data[subtest]['periods'].append(period_label)
                growth_chart_data[subtest]['values'].append(s['growth_percentile'])

            fig_growth = go.Figure()
            for subtest, data in growth_chart_data.items():
                fig_growth.add_trace(go.Scatter(
                    x=data['periods'], y=data['values'],
                    mode='lines+markers', name=subtest,
                ))
            fig_growth.add_hrect(y0=0, y1=35, fillcolor="#dc3545", opacity=0.05, line_width=0)
            fig_growth.add_hrect(y0=35, y1=65, fillcolor="#17a2b8", opacity=0.05, line_width=0)
            fig_growth.add_hrect(y0=65, y1=100, fillcolor="#28a745", opacity=0.05, line_width=0)
            fig_growth.update_layout(
                title='ERB Growth Percentile Over Time',
                yaxis_title='Growth Percentile', yaxis=dict(range=[0, 100]),
                height=350, xaxis=dict(tickangle=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_growth, use_container_width=True)

    # ── Teacher Outputs (Parent Report + Intervention Export) ─────────
    st.subheader("Teacher Outputs")
    out1, out2 = st.columns(2)
    with out1:
        # Polished parent report
        if latest_score:
            components_dict = {
                'reading_component': latest_score.get('reading_component'),
                'phonics_component': latest_score.get('phonics_component'),
                'spelling_component': latest_score.get('spelling_component'),
                'sight_words_component': latest_score.get('sight_words_component'),
            }
            inv_list = []
            if not interventions_df.empty:
                for _, r in interventions_df.head(5).iterrows():
                    inv_list.append(r.to_dict())
            goal_list = []
            if not student_records.empty:
                for sid in student_records['student_id'].tolist():
                    gf = get_student_goals(sid)
                    if not gf.empty:
                        for _, gr in gf.iterrows():
                            goal_list.append(gr.to_dict())

            # Prepare ERB scores for parent report
            erb_report_scores = None
            if erb_summaries:
                erb_report_scores = []
                seen_subtests = set()
                for es in reversed(erb_summaries):  # latest first
                    if es['subtest'] not in seen_subtests:
                        seen_subtests.add(es['subtest'])
                        erb_report_scores.append({
                            'label': es['label'],
                            'stanine': es['stanine'],
                            'percentile': es.get('percentile'),
                            'classification': es.get('classification', ''),
                            'description': ERB_SUBTEST_DESCRIPTIONS.get(es['subtest'], ''),
                        })
                erb_report_scores.reverse()

            report_html = generate_parent_report_html(
                student_name=student_name,
                grade=selected_student_row.get('grade_level', ''),
                teacher=selected_student_row.get('teacher_name', ''),
                school_year=selected_student_row.get('school_year', ''),
                period=latest_score.get('assessment_period', ''),
                overall_score=latest_score.get('overall_literacy_score'),
                risk_level=latest_score.get('risk_level', 'Unknown'),
                components=components_dict,
                interventions=inv_list,
                goals=goal_list if goal_list else None,
                benchmark_status=bm_status,
                erb_scores=erb_report_scores,
            )
            st.download_button(
                'Download Parent Report (HTML/PDF-ready)',
                report_html.encode('utf-8'),
                f"{student_name.lower().replace(' ','_')}_parent_report.html",
                'text/html',
            )
        else:
            st.info("No score data available for parent report.")

    with out2:
        score_val = latest_score.get('overall_literacy_score') if latest_score else 'N/A'
        risk_val = latest_score.get('risk_level') if latest_score else 'N/A'
        html_parts = [
            "<html><head><style>body{font-family:Arial,sans-serif;margin:2em;}h1{color:#333;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:8px;text-align:left;}th{background:#f5f5f5;}</style></head><body>",
            f"<h1>Intervention Plan Summary &mdash; {student_name}</h1>",
            f"<p><strong>Latest Score:</strong> {score_val}</p>",
            f"<p><strong>Risk Level:</strong> {risk_val}</p>",
            "<h2>Interventions</h2>",
        ]
        if not interventions_df.empty:
            html_parts.append("<table><tr><th>Type</th><th>Status</th><th>Start</th><th>End</th></tr>")
            for _, r in interventions_df.head(10).iterrows():
                html_parts.append(
                    f"<tr><td>{r.get('intervention_type','')}</td><td>{r.get('status','')}</td>"
                    f"<td>{r.get('start_date','')}</td><td>{r.get('end_date','')}</td></tr>"
                )
            html_parts.append("</table>")
        else:
            html_parts.append("<p>No interventions logged.</p>")
        html_parts.append("</body></html>")
        html_content = "\n".join(html_parts)
        st.download_button(
            'Intervention plan export (HTML)',
            html_content.encode('utf-8'),
            f"{student_name.lower().replace(' ','_')}_intervention_plan.html",
            'text/html'
        )

    st.markdown("---")
    
    # Assessment History Table
    st.subheader("Assessment History")
    
    if not assessments_df.empty:
        display_assessments = assessments_df[[
            'grade_level', 'school_year', 'assessment_date', 'assessment_type', 'assessment_period',
            'score_value', 'score_normalized', 'notes', 'concerns'
        ]].copy()
        
        display_assessments.columns = [
            'Grade', 'School Year', 'Date', 'Assessment Type', 'Period', 
            'Score', 'Normalized Score', 'Notes', 'Concerns'
        ]
        
        # Format normalized scores
        display_assessments['Normalized Score'] = display_assessments['Normalized Score'].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
        
        st.dataframe(display_assessments, use_container_width=True, height=300)
    else:
        st.info("No assessment history available.")
    
    st.markdown("---")
    
    # Intervention Timeline - already fetched above, just display
    
    if not interventions_df.empty:
        display_interventions = interventions_df[[
            'grade_level', 'school_year', 'intervention_type', 'start_date', 'end_date',
            'frequency', 'duration_minutes', 'status', 'notes'
        ]].copy()
        
        display_interventions.columns = [
            'Grade', 'School Year', 'Type', 'Start Date', 'End Date', 
            'Frequency', 'Duration (min)', 'Status', 'Notes'
        ]
        
        st.dataframe(display_interventions, use_container_width=True)
    else:
        st.info("No intervention records for this student.")
    
    # Actions
    st.markdown("---")
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("Add Assessment", use_container_width=True):
            st.session_state['redirect_to_entry'] = True
            st.session_state['entry_student_name'] = student_name
            # Pre-select the most recent grade
            if not student_records.empty:
                latest_grade = student_records.iloc[-1]['grade_level']
                st.session_state['entry_grade_prefill'] = latest_grade
            st.rerun()
    
    with action_col2:
        if st.button("Add Intervention", use_container_width=True):
            st.session_state['add_intervention'] = True
            st.session_state['intervention_student_name'] = student_name
