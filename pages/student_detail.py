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
        WHERE s.student_name = ?
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
                WHERE s.class_name = ? AND s.school_year = ?
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
    
    # Initialize interventions_df so it's available for timeline/export even without scores
    interventions_df = pd.DataFrame()

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
            benchmark_status = "Above" if overall_score >= 70 else ("At" if overall_score >= 50 else "Below")
            st.metric("Benchmark Status", benchmark_status)
        
        # Get active interventions (using student_name query)
        conn = get_db_connection()
        interventions_query = '''
            SELECT i.*, s.student_name, s.grade_level, s.school_year
            FROM interventions i
            JOIN students s ON i.student_id = s.student_id
            WHERE s.student_name = ?
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
        WHERE s.student_name = ?
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
                # Enhanced progress chart showing all grades/years
                import plotly.graph_objects as go
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=scores_df['period_label'],
                    y=scores_df['overall_literacy_score'],
                    mode='lines+markers',
                    name='Literacy Score',
                    line=dict(color='#007bff', width=3),
                    marker=dict(size=12)
                ))
                
                # Add benchmark line
                fig.add_hline(y=70, line_dash="dash", line_color="green", 
                              annotation_text="Benchmark (70)", annotation_position="right")
                
                fig.update_layout(
                    title='Student Progress Across All Grades',
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

    st.subheader("Teacher Outputs")
    out1, out2 = st.columns(2)
    with out1:
        if st.button('Parent-ready summary'):
            score_text = f"{latest_score.get('overall_literacy_score', 'N/A'):.1f}" if latest_score and latest_score.get('overall_literacy_score') is not None else 'N/A'
            risk_text = latest_score.get('risk_level', 'Unknown') if latest_score else 'Unknown'
            trend_text = latest_score.get('trend', 'Unknown') if latest_score else 'Unknown'
            st.success(f"{student_name} currently has a literacy score of {score_text}, risk level {risk_text}, and trend {trend_text}. Instruction should continue targeting identified needs and progress checks should continue regularly.")
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
            'Intervention plan summary export (HTML/PDF-ready)',
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
