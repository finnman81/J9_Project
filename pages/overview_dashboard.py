"""
Overview Dashboard Page
Shows KPIs, graphs, and sortable student table
"""
import streamlit as st
import pandas as pd
import numpy as np
from database import get_all_students, get_db_connection
from visualizations import (
    create_risk_distribution_chart,
    create_grade_comparison_chart,
    create_score_trend_chart
)
from calculations import determine_risk_level

def show_overview_dashboard():
    st.title("📊 Overview Dashboard")
    st.markdown("---")
    
    # Get database connection
    conn = get_db_connection()
    
    # Get unique values for filters
    students_df = get_all_students()
    all_grade_levels = sorted(students_df['grade_level'].unique().tolist())
    classes = ['All'] + sorted([c for c in students_df['class_name'].dropna().unique() if c])
    teachers = ['All'] + sorted([t for t in students_df['teacher_name'].dropna().unique() if t])
    school_years = ['All'] + sorted(students_df['school_year'].unique().tolist())
    
    # Main page filters
    st.subheader("Filters")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    
    with filter_col1:
        selected_grades = st.multiselect(
            "Grade Levels",
            all_grade_levels,
            default=all_grade_levels,
            help="Select one or more grade levels to display"
        )
        # If no grades selected, show all
        if not selected_grades:
            selected_grades = all_grade_levels
        # Convert to single grade for backward compatibility with query
        selected_grade = selected_grades[0] if len(selected_grades) == 1 else 'All'
    
    with filter_col2:
        selected_class = st.selectbox("Class", classes)
    
    with filter_col3:
        selected_teacher = st.selectbox("Teacher", teachers)
    
    with filter_col4:
        selected_year = st.selectbox("School Year", school_years)
    
    # Sidebar filters (keep for additional filtering options)
    st.sidebar.header("Additional Filters")
    st.sidebar.info("Use main page filters above for primary filtering")
    
    # Build query: use each student's most recent year (and latest period in that year) by default
    # When a specific year is selected, filter to that year; otherwise use latest year per student
    conditions = []
    params = []
    
    # Handle multi-select grades
    if selected_grades:
        if len(selected_grades) == 1:
            conditions.append('s.grade_level = %s')
            params.append(selected_grades[0])
        else:
            placeholders = ','.join(['%s'] * len(selected_grades))
            conditions.append(f's.grade_level IN ({placeholders})')
            params.extend(selected_grades)
    elif selected_grade and selected_grade != 'All':
        conditions.append('s.grade_level = %s')
        params.append(selected_grade)
    
    if selected_class != 'All':
        conditions.append('s.class_name = %s')
        params.append(selected_class)
    if selected_teacher != 'All':
        conditions.append('s.teacher_name = %s')
        params.append(selected_teacher)
    
    where_clause = ' AND '.join(conditions) if conditions else '1=1'
    
    if selected_year != 'All':
        # Specific year: filter students and scores to that year, latest period per student
        conditions.append('s.school_year = %s')
        params.append(selected_year)
        where_clause = ' AND '.join(conditions)
        query = f'''
            SELECT 
                s.student_id,
                s.student_name,
                s.grade_level,
                s.class_name,
                s.teacher_name,
                s.school_year,
                ls.overall_literacy_score,
                ls.risk_level,
                ls.trend,
                ls.assessment_period,
                ls.calculated_at
            FROM students s
            LEFT JOIN literacy_scores ls ON s.student_id = ls.student_id
                AND ls.school_year = s.school_year
                AND ls.score_id = (
                    SELECT score_id FROM literacy_scores ls2
                    WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
                    ORDER BY ls2.calculated_at DESC LIMIT 1
                )
            WHERE {where_clause}
            ORDER BY s.student_name, s.grade_level
        '''
    else:
        # All years: one row per student (name) using their most recent school year and latest period
        query = f'''
            SELECT 
                s.student_id,
                s.student_name,
                s.grade_level,
                s.class_name,
                s.teacher_name,
                s.school_year,
                ls.overall_literacy_score,
                ls.risk_level,
                ls.trend,
                ls.assessment_period,
                ls.calculated_at
            FROM students s
            LEFT JOIN literacy_scores ls ON ls.student_id = s.student_id
                AND ls.school_year = s.school_year
                AND ls.score_id = (
                    SELECT score_id FROM literacy_scores ls2
                    WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
                    ORDER BY ls2.calculated_at DESC LIMIT 1
                )
            WHERE {where_clause}
              AND s.school_year = (
                  SELECT MAX(s2.school_year) FROM students s2
                  WHERE s2.student_name = s.student_name
              )
            ORDER BY s.student_name, s.grade_level
        '''
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # KPIs Section
    st.subheader("Key Performance Indicators")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_students = len(df['student_id'].unique())
    at_risk = len(df[df['risk_level'].isin(['High', 'Medium'])]) if 'risk_level' in df.columns else 0
    avg_score = df['overall_literacy_score'].mean() if 'overall_literacy_score' in df.columns else 0
    
    # Get intervention coverage
    conn = get_db_connection()
    intervention_query = '''
        SELECT COUNT(DISTINCT student_id) as intervention_count
        FROM interventions
        WHERE status = 'Active'
    '''
    if selected_year != 'All':
        # Filter by students in selected year
        intervention_query = '''
            SELECT COUNT(DISTINCT i.student_id) as intervention_count
            FROM interventions i
            JOIN students s ON i.student_id = s.student_id
            WHERE i.status = 'Active' AND s.school_year = %s
        '''
        intervention_df = pd.read_sql_query(intervention_query, conn, params=[selected_year])
    else:
        intervention_df = pd.read_sql_query(intervention_query, conn)
    conn.close()
    
    intervention_count = intervention_df['intervention_count'].iloc[0] if not intervention_df.empty else 0

    # Coverage should be at-risk students who have an active intervention / at-risk students
    at_risk_with_intervention_query = '''
        SELECT COUNT(DISTINCT s.student_id) AS covered_at_risk
        FROM students s
        JOIN literacy_scores ls ON ls.student_id = s.student_id AND ls.school_year = s.school_year
        LEFT JOIN interventions i ON i.student_id = s.student_id AND i.status = 'Active'
        WHERE ls.score_id = (
            SELECT score_id FROM literacy_scores ls2
            WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
            ORDER BY ls2.calculated_at DESC
            LIMIT 1
        )
          AND ls.risk_level IN ('High', 'Medium')
    '''
    at_risk_params = []
    if selected_year != 'All':
        at_risk_with_intervention_query += ' AND s.school_year = %s'
        at_risk_params.append(selected_year)

    at_risk_with_intervention_query += ' AND i.student_id IS NOT NULL'
    conn = get_db_connection()
    at_risk_with_intervention_df = pd.read_sql_query(
        at_risk_with_intervention_query,
        conn,
        params=at_risk_params
    )
    conn.close()
    covered_at_risk = (
        at_risk_with_intervention_df['covered_at_risk'].iloc[0]
        if not at_risk_with_intervention_df.empty else 0
    )

    intervention_coverage = (covered_at_risk / at_risk * 100) if at_risk > 0 else 0
    
    # Assessment completion rate
    students_with_scores = len(df[df['overall_literacy_score'].notna()])
    completion_rate = (students_with_scores / total_students * 100) if total_students > 0 else 0
    
    with col1:
        st.metric("Total Students", total_students)
    
    with col2:
        st.metric("Students at Risk", at_risk, delta=None)
    
    with col3:
        st.metric("Avg Literacy Score", f"{avg_score:.1f}" if avg_score else "N/A")
    
    with col4:
        st.metric("Intervention Coverage", f"{intervention_coverage:.1f}%")
    
    with col5:
        st.metric("Assessment Completion", f"{completion_rate:.1f}%")
    
    st.markdown("---")
    
    # Charts Section
    st.subheader("Analytics & Insights")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        if not df.empty and 'risk_level' in df.columns:
            # Use first selected grade or None for chart
            chart_grade_filter = selected_grades[0] if selected_grades and len(selected_grades) == 1 else None
            risk_chart = create_risk_distribution_chart(df, chart_grade_filter)
            st.plotly_chart(risk_chart, use_container_width=True)
        else:
            st.info("No risk level data available")
    
    with chart_col2:
        if not df.empty and 'overall_literacy_score' in df.columns:
            grade_chart = create_grade_comparison_chart(df)
            st.plotly_chart(grade_chart, use_container_width=True)
        else:
            st.info("No score data available")
    
    # Trend chart (full width)
    if selected_year != 'All':
        trend_df = df.copy()
        trend_df['school_year'] = selected_year
        trend_chart = create_score_trend_chart(trend_df, selected_year)
        st.plotly_chart(trend_chart, use_container_width=True)
    
    st.markdown("---")
    
    # Additional Graphs Section
    st.subheader("Additional Analytics")
    
    add_chart_col1, add_chart_col2 = st.columns(2)
    
    with add_chart_col1:
        # Score Distribution Histogram
        if not df.empty and 'overall_literacy_score' in df.columns:
            scores_clean = df['overall_literacy_score'].dropna()
            if not scores_clean.empty:
                import plotly.graph_objects as go
                import numpy as np
                
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(
                    x=scores_clean,
                    nbinsx=20,
                    marker_color='#007bff',
                    opacity=0.7,
                    name='Literacy Scores'
                ))
                
                # Add benchmark lines
                fig_dist.add_vline(x=70, line_dash="dash", line_color="green", 
                                  annotation_text="Benchmark (70)", annotation_position="top")
                fig_dist.add_vline(x=50, line_dash="dash", line_color="orange", 
                                  annotation_text="At Risk Threshold (50)", annotation_position="top")
                
                fig_dist.update_layout(
                    title='Literacy Score Distribution',
                    xaxis_title='Literacy Score',
                    yaxis_title='Number of Students',
                    height=400,
                    xaxis=dict(range=[0, 100])
                )
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                st.info("No score data available for distribution")
        else:
            st.info("No score data available")
    
    with add_chart_col2:
        # Risk Level Trends Over Time (if multiple periods available)
        if not df.empty and 'risk_level' in df.columns and 'assessment_period' in df.columns:
            # Risk level by year: one count per student per year (latest period), grouped by school_year
            conn = get_db_connection()
            risk_trend_query = '''
                SELECT school_year, risk_level, COUNT(*) as count
                FROM (
                    SELECT ls.student_id, ls.school_year, ls.risk_level,
                           ROW_NUMBER() OVER (PARTITION BY ls.student_id, ls.school_year ORDER BY ls.calculated_at DESC) as rn
                    FROM literacy_scores ls
                    JOIN students s ON ls.student_id = s.student_id
            '''
            trend_conditions = []
            trend_params = []
            
            if selected_grades:
                if len(selected_grades) > 1:
                    placeholders = ','.join(['%s'] * len(selected_grades))
                    trend_conditions.append(f's.grade_level IN ({placeholders})')
                    trend_params.extend(selected_grades)
                else:
                    trend_conditions.append('s.grade_level = %s')
                    trend_params.append(selected_grades[0])
            
            # Always show all years for this chart (ignore School Year filter)
            
            if trend_conditions:
                risk_trend_query += ' WHERE ' + ' AND '.join(trend_conditions)
            
            risk_trend_query += '''
                ) sub WHERE rn = 1
                GROUP BY school_year, risk_level
                ORDER BY school_year, risk_level
            '''
            
            risk_trend_df = pd.read_sql_query(risk_trend_query, conn, params=trend_params)
            conn.close()
            
            if not risk_trend_df.empty and len(risk_trend_df['school_year'].unique()) >= 1:
                import plotly.graph_objects as go
                
                fig_risk_trend = go.Figure()
                
                risk_levels = ['Low', 'Medium', 'High']
                colors = {'Low': '#28a745', 'Medium': '#ffc107', 'High': '#dc3545'}
                
                for risk in risk_levels:
                    risk_data = risk_trend_df[risk_trend_df['risk_level'] == risk]
                    if not risk_data.empty:
                        fig_risk_trend.add_trace(go.Scatter(
                            x=risk_data['school_year'],
                            y=risk_data['count'],
                            mode='lines+markers',
                            name=risk,
                            line=dict(color=colors.get(risk, '#6c757d'), width=3),
                            marker=dict(size=10)
                        ))
                
                fig_risk_trend.update_layout(
                    title='Risk Level Trends by Year',
                    xaxis_title='School Year',
                    yaxis_title='Number of Students',
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_risk_trend, use_container_width=True)
            else:
                # Fallback: Show intervention effectiveness if available
                conn = get_db_connection()
                intervention_effect_query = '''
                    SELECT 
                        s.grade_level,
                        COUNT(DISTINCT CASE WHEN i.status = 'Active' THEN i.student_id END) as with_intervention,
                        COUNT(DISTINCT s.student_id) as total_students
                    FROM students s
                    LEFT JOIN interventions i ON s.student_id = i.student_id
                '''
                int_conditions = []
                int_params = []
                
                if selected_grades:
                    if len(selected_grades) > 1:
                        placeholders = ','.join(['%s'] * len(selected_grades))
                        int_conditions.append(f's.grade_level IN ({placeholders})')
                        int_params.extend(selected_grades)
                    else:
                        int_conditions.append('s.grade_level = %s')
                        int_params.append(selected_grades[0])
                
                if int_conditions:
                    intervention_effect_query += ' WHERE ' + ' AND '.join(int_conditions)
                
                intervention_effect_query += ' GROUP BY s.grade_level'
                
                int_effect_df = pd.read_sql_query(intervention_effect_query, conn, params=int_params)
                conn.close()
                
                if not int_effect_df.empty:
                    import plotly.graph_objects as go
                    
                    int_effect_df['intervention_rate'] = (int_effect_df['with_intervention'] / int_effect_df['total_students'] * 100)
                    
                    fig_int = go.Figure()
                    fig_int.add_trace(go.Bar(
                        x=int_effect_df['grade_level'],
                        y=int_effect_df['intervention_rate'],
                        marker_color='#17a2b8',
                        text=[f"{x:.1f}%" for x in int_effect_df['intervention_rate']],
                        textposition='auto',
                        name='Intervention Rate'
                    ))
                    
                    fig_int.update_layout(
                        title='Intervention Coverage by Grade',
                        xaxis_title='Grade Level',
                        yaxis_title='% of Students with Interventions',
                        height=400,
                        yaxis=dict(range=[0, 100])
                    )
                    st.plotly_chart(fig_int, use_container_width=True)
                else:
                    st.info("No intervention data available")
        else:
            st.info("No trend data available")
    

    # Enhancement additions (keeps original dashboard and extends it)
    st.subheader("Data Freshness & Completeness")
    fresh_col1, fresh_col2 = st.columns(2)
    latest_update = pd.to_datetime(df['calculated_at'], errors='coerce').max() if not df.empty else None
    with fresh_col1:
        st.metric("Last Updated", latest_update.strftime('%Y-%m-%d %H:%M') if pd.notna(latest_update) else "N/A")
        st.metric("% Students w/ Latest Assessment", f"{completion_rate:.1f}%")
    with fresh_col2:
        conn = get_db_connection()
        missing_q = "SELECT s.grade_level, COALESCE(s.class_name,'Unassigned') as class_name, COUNT(DISTINCT s.student_id) as missing_entries FROM students s LEFT JOIN literacy_scores ls ON ls.student_id=s.student_id AND ls.school_year=s.school_year WHERE " + where_clause + " AND ls.score_id IS NULL GROUP BY s.grade_level, s.class_name ORDER BY s.grade_level, s.class_name"
        missing_df = pd.read_sql_query(missing_q, conn, params=params)
        conn.close()
        st.write("Missing entries by grade/class")
        st.dataframe(missing_df if not missing_df.empty else pd.DataFrame({'status':['No missing entries']}), use_container_width=True, height=140)

    st.subheader("Teacher & Admin Insights")
    conn = get_db_connection()
    history_q = "SELECT s.student_id, s.student_name, s.school_year, ls.assessment_period, ls.risk_level, ls.overall_literacy_score, ls.reading_component, ls.phonics_component, ls.sight_words_component, ls.calculated_at FROM students s JOIN literacy_scores ls ON ls.student_id=s.student_id AND ls.school_year=s.school_year WHERE " + where_clause
    hist_df = pd.read_sql_query(history_q, conn, params=params)
    measure_q = "SELECT s.student_id, a.assessment_type, a.score_normalized FROM students s JOIN assessments a ON a.student_id=s.student_id WHERE " + where_clause
    measure_df = pd.read_sql_query(measure_q, conn, params=params)
    interv_q = "SELECT s.student_id, i.intervention_type, i.status FROM students s LEFT JOIN interventions i ON i.student_id=s.student_id WHERE " + where_clause
    i_df = pd.read_sql_query(interv_q, conn, params=params)
    conn.close()

    ins_col1, ins_col2 = st.columns(2)
    with ins_col1:
        moves = {'Green→Yellow': 0, 'Yellow→Red': 0, 'Green→Red': 0}
        if not hist_df.empty:
            order = {'Fall':1,'Winter':2,'Spring':3,'EOY':4}
            tmp = hist_df.copy()
            tmp['period_order'] = tmp['assessment_period'].map(order).fillna(0)
            tmp = tmp.sort_values(['student_id','school_year','period_order','calculated_at'])
            for _, g in tmp.groupby(['student_id','school_year']):
                if len(g) >= 2:
                    prev, curr = g.iloc[-2]['risk_level'], g.iloc[-1]['risk_level']
                    t = f"{'Green' if prev=='Low' else 'Yellow' if prev=='Medium' else 'Red'}→{'Green' if curr=='Low' else 'Yellow' if curr=='Medium' else 'Red'}"
                    if t in moves:
                        moves[t] += 1
        st.markdown("**Cohort movement since last window**")
        st.dataframe(pd.DataFrame([moves]), use_container_width=True, height=100)
        st.markdown("**Risk distribution by measure**")
        at_risk_ids = df[df['risk_level'].isin(['High','Medium'])]['student_id'].unique().tolist()
        risk_measure = measure_df[measure_df['student_id'].isin(at_risk_ids)] if at_risk_ids else pd.DataFrame()
        if not risk_measure.empty:
            rm = risk_measure.groupby('assessment_type', as_index=False)['score_normalized'].mean().sort_values('score_normalized')
            st.bar_chart(rm.set_index('assessment_type'))
    with ins_col2:
        warn_rows = []
        fc_rows = []
        grp_rows = []
        if not hist_df.empty:
            order = {'Fall':1,'Winter':2,'Spring':3,'EOY':4}
            tmp = hist_df.copy(); tmp['x'] = tmp['assessment_period'].map(order).fillna(0)
            tmp = tmp.sort_values(['student_id','school_year','x'])
            for sid, g in tmp.groupby('student_id'):
                scores = g['overall_literacy_score'].dropna().tolist()
                if len(scores) >= 3:
                    flags = []
                    if scores[-1] < scores[-2] < scores[-3]:
                        flags.append('2 consecutive drops')
                    if abs(scores[-1] - scores[-3]) <= 1:
                        flags.append('flatline across 3 windows')
                    if np.std(scores[-3:]) >= 8:
                        flags.append('high variance')
                    if flags:
                        warn_rows.append({'student': g.iloc[-1]['student_name'], 'flags': ', '.join(flags)})
                gg = g.dropna(subset=['overall_literacy_score'])
                if len(gg) >= 2:
                    m, b = np.polyfit(gg['x'], gg['overall_literacy_score'], 1)
                    pred = m * 4 + b
                    band = max(5, gg['overall_literacy_score'].std() if len(gg) > 2 else 8)
                    fc_rows.append({'student': gg.iloc[-1]['student_name'], 'estimated_eoy': round(pred, 1), 'band': f"±{band:.1f}"})

                    # Identify weakest component for grouping
                    latest_row = gg.iloc[-1]
                    component_scores = {
                        'reading': latest_row.get('reading_component', 100),
                        'phonics': latest_row.get('phonics_component', 100),
                        'sight_words': latest_row.get('sight_words_component', 100),
                    }
                    # Replace NaN with 100 (treat missing as non-weak)
                    component_scores = {k: (v if pd.notna(v) else 100) for k, v in component_scores.items()}
                    weakness = min(component_scores, key=component_scores.get)
                    grp_rows.append({'student': latest_row['student_name'], 'group': f"{latest_row['risk_level']} + {weakness}"})
        st.markdown("**Early warning flags**")
        st.dataframe(pd.DataFrame(warn_rows), use_container_width=True, height=120)
        st.markdown("**Forecast + recommended groupings**")
        st.dataframe(pd.DataFrame(fc_rows).head(8), use_container_width=True, height=100)
        st.dataframe(pd.DataFrame(grp_rows).head(8), use_container_width=True, height=100)

    st.subheader("Admin Views")
    admin_col1, admin_col2 = st.columns(2)
    with admin_col1:
        if not i_df.empty:
            merged = i_df.merge(df[['student_id','trend']], on='student_id', how='left')
            eff = merged.groupby('intervention_type', as_index=False).agg(sample_size=('student_id','nunique'), responders=('trend', lambda s: (s=='Improving').mean()*100))
            eff['avg_growth_rate'] = eff['responders']/20
            st.dataframe(eff, use_container_width=True, height=160)
    with admin_col2:
        tiers = df['risk_level'].map({'Low':'Tier 1','Medium':'Tier 2','High':'Tier 3'}).fillna('Unknown').value_counts().rename_axis('tier').reset_index(name='count')
        st.dataframe(tiers, use_container_width=True, height=160)

    printable = df[['student_name','grade_level','class_name','teacher_name','overall_literacy_score','risk_level']].copy()
    st.download_button('Download Printable Grade/Class Report (CSV)', printable.to_csv(index=False), 'grade_class_report.csv', 'text/csv')

    all_students_df = get_all_students()
    subgroup_cols = [c for c in ['SPED','ELL','FRL'] if c in all_students_df.columns]
    if subgroup_cols:
        st.markdown("### Equity lens (optional)")
        subgroup_df = df.merge(all_students_df[['student_id'] + subgroup_cols], on='student_id', how='left')
        parts=[]
        for col in subgroup_cols:
            tmp = subgroup_df.groupby(col)['risk_level'].apply(lambda s: (s.isin(['High','Medium']).mean()*100)).reset_index(name='at_risk_pct')
            tmp['subgroup'] = col
            parts.append(tmp)
        st.dataframe(pd.concat(parts, ignore_index=True), use_container_width=True)

    st.markdown("---")
    
    # Student Table Section
    st.subheader("Student List")
    
    # Prepare table data
    display_df = df[['student_name', 'grade_level', 'class_name', 'teacher_name', 
                      'overall_literacy_score', 'risk_level', 'trend', 'assessment_period']].copy()
    
    display_df.columns = ['Student Name', 'Grade', 'Class', 'Teacher', 
                          'Literacy Score', 'Risk Level', 'Trend', 'Last Assessment']
    
    # Format scores
    if 'Literacy Score' in display_df.columns:
        display_df['Literacy Score'] = display_df['Literacy Score'].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
    
    # Add color coding for risk levels
    def color_risk_level(val):
        if val == 'High':
            return 'background-color: #dc3545; color: white'
        elif val == 'Medium':
            return 'background-color: #ffc107; color: black'
        elif val == 'Low':
            return 'background-color: #28a745; color: white'
        return ''
    
    # Display table
    if not display_df.empty:
        styled_df = display_df.style.applymap(color_risk_level, subset=['Risk Level'])
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"literacy_overview_{selected_year if selected_year != 'All' else 'all'}.csv",
            mime="text/csv"
        )
    else:
        st.info("No students found with the selected filters.")
