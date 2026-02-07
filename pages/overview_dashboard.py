"""
Overview Dashboard Page
Clean, scannable layout for teachers and administrators.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from database import get_all_students, get_db_connection
from calculations import determine_risk_level
from benchmarks import (
    get_benchmark_status, get_support_level, benchmark_color,
    benchmark_emoji, group_students,
)
from erb_scoring import (
    ERB_SUBTESTS, ERB_SUBTEST_LABELS, summarize_erb_scores,
    get_latest_erb_tier, blend_tiers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPORT_LABEL = {'High': 'Needs Support', 'Medium': 'Monitor', 'Low': 'On Track'}
_SUPPORT_COLOR = {
    'Needs Support': 'background-color: #f5c6cb; color: #721c24',
    'Monitor':       'background-color: #ffeeba; color: #856404',
    'On Track':      'background-color: #c3e6cb; color: #155724',
}

def _support_label(risk: str) -> str:
    return _SUPPORT_LABEL.get(risk, risk or 'N/A')


def _color_support(val):
    return _SUPPORT_COLOR.get(val, '')


def _color_tier(val):
    if 'Core' in str(val):
        return 'background-color: #c3e6cb; color: #155724'
    elif 'Strategic' in str(val):
        return 'background-color: #ffeeba; color: #856404'
    elif 'Intensive' in str(val):
        return 'background-color: #f5c6cb; color: #721c24'
    return ''

# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

def show_overview_dashboard():
    st.title("Literacy Dashboard")

    # ── Filters ───────────────────────────────────────────────────────────
    students_df = get_all_students()
    all_grade_levels = sorted(students_df['grade_level'].unique().tolist())
    classes = ['All'] + sorted([c for c in students_df['class_name'].dropna().unique() if c])
    teachers = ['All'] + sorted([t for t in students_df['teacher_name'].dropna().unique() if t])
    school_years = ['All'] + sorted(students_df['school_year'].unique().tolist())

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        selected_grades = st.multiselect("Grade", all_grade_levels, default=all_grade_levels)
        if not selected_grades:
            selected_grades = all_grade_levels
    with f2:
        selected_class = st.selectbox("Class", classes)
    with f3:
        selected_teacher = st.selectbox("Teacher", teachers)
    with f4:
        selected_year = st.selectbox("School Year", school_years)

    # ── Query construction ────────────────────────────────────────────────
    conn = get_db_connection()
    conditions = []
    params = []

    if selected_grades:
        if len(selected_grades) == 1:
            conditions.append('s.grade_level = %s')
            params.append(selected_grades[0])
        else:
            placeholders = ','.join(['%s'] * len(selected_grades))
            conditions.append(f's.grade_level IN ({placeholders})')
            params.extend(selected_grades)

    if selected_class != 'All':
        conditions.append('s.class_name = %s'); params.append(selected_class)
    if selected_teacher != 'All':
        conditions.append('s.teacher_name = %s'); params.append(selected_teacher)

    where_clause = ' AND '.join(conditions) if conditions else '1=1'

    if selected_year != 'All':
        conditions.append('s.school_year = %s'); params.append(selected_year)
        where_clause = ' AND '.join(conditions)
        query = f'''
            SELECT s.student_id, s.student_name, s.grade_level, s.class_name,
                   s.teacher_name, s.school_year,
                   ls.overall_literacy_score, ls.risk_level, ls.trend,
                   ls.assessment_period, ls.calculated_at
            FROM students s
            LEFT JOIN literacy_scores ls ON s.student_id = ls.student_id
                AND ls.school_year = s.school_year
                AND ls.score_id = (
                    SELECT score_id FROM literacy_scores ls2
                    WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
                    ORDER BY ls2.calculated_at DESC LIMIT 1)
            WHERE {where_clause}
            ORDER BY s.student_name, s.grade_level
        '''
    else:
        query = f'''
            SELECT s.student_id, s.student_name, s.grade_level, s.class_name,
                   s.teacher_name, s.school_year,
                   ls.overall_literacy_score, ls.risk_level, ls.trend,
                   ls.assessment_period, ls.calculated_at
            FROM students s
            LEFT JOIN literacy_scores ls ON ls.student_id = s.student_id
                AND ls.school_year = s.school_year
                AND ls.score_id = (
                    SELECT score_id FROM literacy_scores ls2
                    WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
                    ORDER BY ls2.calculated_at DESC LIMIT 1)
            WHERE {where_clause}
              AND s.school_year = (
                  SELECT MAX(s2.school_year) FROM students s2
                  WHERE s2.student_name = s.student_name)
            ORDER BY s.student_name, s.grade_level
        '''

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    # ── Compute KPI values ────────────────────────────────────────────────
    total_students = len(df['student_id'].unique())
    needs_support = len(df[df['risk_level'].isin(['High', 'Medium'])]) if 'risk_level' in df.columns else 0
    avg_score = df['overall_literacy_score'].mean() if 'overall_literacy_score' in df.columns else 0
    students_with_scores = len(df[df['overall_literacy_score'].notna()])
    completion_rate = (students_with_scores / total_students * 100) if total_students > 0 else 0

    # Intervention coverage
    conn = get_db_connection()
    cov_q = '''
        SELECT COUNT(DISTINCT s.student_id) AS covered
        FROM students s
        JOIN literacy_scores ls ON ls.student_id = s.student_id AND ls.school_year = s.school_year
        JOIN interventions i ON i.student_id = s.student_id AND i.status = 'Active'
        WHERE ls.score_id = (
            SELECT score_id FROM literacy_scores ls2
            WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
            ORDER BY ls2.calculated_at DESC LIMIT 1)
          AND ls.risk_level IN ('High', 'Medium')
    '''
    cov_params = []
    if selected_year != 'All':
        cov_q += ' AND s.school_year = %s'
        cov_params.append(selected_year)
    cov_df = pd.read_sql_query(cov_q, conn, params=cov_params)
    conn.close()
    covered = cov_df['covered'].iloc[0] if not cov_df.empty else 0
    coverage_text = f"{covered} of {needs_support}" if needs_support > 0 else "N/A"

    # ── KPI Cards ─────────────────────────────────────────────────────────
    st.markdown("")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total Students", total_students)
    with k2:
        st.metric("Needs Support", needs_support)
    with k3:
        st.metric("Average Score", f"{avg_score:.1f}" if avg_score else "N/A")
    with k4:
        st.metric("Intervention Coverage", coverage_text)
    with k5:
        st.metric("Assessed", f"{completion_rate:.0f}%")

    # ── Charts (two-column) ───────────────────────────────────────────────
    st.markdown("")
    ch1, ch2 = st.columns(2)

    with ch1:
        # Score distribution histogram
        if not df.empty and 'overall_literacy_score' in df.columns:
            scores = df['overall_literacy_score'].dropna()
            if not scores.empty:
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=scores, nbinsx=15,
                    marker_color='#5b9bd5', opacity=0.85,
                    name='Students',
                ))
                fig.add_vline(x=70, line_dash="dash", line_color="#28a745",
                              annotation_text="Benchmark", annotation_position="top")
                fig.add_vline(x=50, line_dash="dash", line_color="#e67e22",
                              annotation_text="Support Threshold", annotation_position="top")
                fig.update_layout(
                    title='Score Distribution',
                    xaxis_title='Literacy Score', yaxis_title='Students',
                    height=370, margin=dict(t=40, b=40),
                    xaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig, use_container_width=True)

    with ch2:
        # Average score by grade (clean bars, no error bars)
        if not df.empty and 'overall_literacy_score' in df.columns:
            grade_avg = df.groupby('grade_level')['overall_literacy_score'].mean().reset_index()
            grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth']
            grade_avg['sort'] = grade_avg['grade_level'].apply(
                lambda g: grade_order.index(g) if g in grade_order else len(grade_order))
            grade_avg = grade_avg.sort_values('sort')

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=grade_avg['grade_level'],
                y=grade_avg['overall_literacy_score'],
                marker_color='#5b9bd5',
                text=[f"{v:.0f}" for v in grade_avg['overall_literacy_score']],
                textposition='outside',
            ))
            fig.add_hline(y=70, line_dash="dash", line_color="#28a745",
                          annotation_text="Benchmark", annotation_position="right")
            fig.update_layout(
                title='Average Score by Grade',
                xaxis_title='', yaxis_title='Average Score',
                height=370, margin=dict(t=40, b=40),
                yaxis=dict(range=[0, 105]),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Support Tiers ─────────────────────────────────────────────────────
    st.markdown("")
    st.subheader("Support Tiers")
    st.caption("Students are grouped into tiers based on benchmark performance. "
               "Core = on track, Strategic = needs targeted help, Intensive = needs significant intervention.")

    if not df.empty:
        grouping_df = group_students(df, df)

        if not grouping_df.empty and 'support_level' in grouping_df.columns:
            # Blend with ERB if available
            try:
                conn = get_db_connection()
                all_assess_df = pd.read_sql_query(
                    '''SELECT a.student_id, a.assessment_type, a.assessment_period,
                              a.score_value, a.school_year, s.student_name, s.grade_level
                       FROM assessments a JOIN students s ON a.student_id = s.student_id
                       ORDER BY a.created_at''', conn)
                conn.close()
            except Exception:
                all_assess_df = pd.DataFrame()

            erb_tier_map = {}
            erb_stanine_map = {}
            if not all_assess_df.empty:
                for sname in grouping_df['student_name'].unique():
                    sa = all_assess_df[all_assess_df['student_name'] == sname]
                    erb_sums = summarize_erb_scores(sa, sname)
                    if erb_sums:
                        erb_tier_map[sname] = get_latest_erb_tier(erb_sums)
                        stans = [s['stanine'] for s in erb_sums if s.get('stanine')]
                        if stans:
                            erb_stanine_map[sname] = round(sum(stans) / len(stans), 1)

            if erb_tier_map:
                grouping_df['erb_tier'] = grouping_df['student_name'].map(erb_tier_map).fillna('Unknown')
                grouping_df['erb_avg_stanine'] = grouping_df['student_name'].map(erb_stanine_map)
                grouping_df['blended_tier'] = grouping_df.apply(
                    lambda r: blend_tiers(r['support_level'], r['erb_tier']), axis=1)
            else:
                grouping_df['erb_tier'] = 'N/A'
                grouping_df['erb_avg_stanine'] = None
                grouping_df['blended_tier'] = grouping_df['support_level']

            tier_col = 'blended_tier'
            tier_counts = grouping_df[tier_col].value_counts()

            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                st.metric("Core", tier_counts.get('Core (Tier 1)', 0),
                          help="On track -- continue effective core instruction")
            with tc2:
                st.metric("Strategic", tier_counts.get('Strategic (Tier 2)', 0),
                          help="Below benchmark -- needs targeted supplemental support")
            with tc3:
                st.metric("Intensive", tier_counts.get('Intensive (Tier 3)', 0),
                          help="Well below benchmark -- needs significant intervention")

            # Build display table
            display_cols = ['student_name', 'grade_level', 'score', 'benchmark_status']
            display_names = ['Student', 'Grade', 'Score', 'Benchmark Status']
            has_erb = 'erb_avg_stanine' in grouping_df.columns and grouping_df['erb_avg_stanine'].notna().any()
            if has_erb:
                display_cols += ['erb_avg_stanine', 'erb_tier']
                display_names += ['ERB Stanine', 'ERB Tier']
            display_cols += [tier_col, 'weakest_skill']
            display_names += ['Support Tier', 'Focus Area']

            tbl = grouping_df[display_cols].copy()
            tbl.columns = display_names
            tbl['Score'] = tbl['Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
            if has_erb:
                tbl['ERB Stanine'] = tbl['ERB Stanine'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "--")
            tbl['Focus Area'] = tbl['Focus Area'].fillna('--')
            tbl = tbl.sort_values(['Support Tier', 'Student'])

            style_cols = ['Support Tier']
            if has_erb and 'ERB Tier' in tbl.columns:
                style_cols.append('ERB Tier')
            styled = tbl.style.map(_color_tier, subset=style_cols)
            st.dataframe(styled, use_container_width=True, height=300)

            st.download_button('Download Grouping Report (CSV)',
                               grouping_df.to_csv(index=False),
                               'support_tiers.csv', 'text/csv')

    # ── Student Roster ────────────────────────────────────────────────────
    st.markdown("")
    st.subheader("Student Roster")

    if not df.empty:
        roster = df[['student_name', 'grade_level', 'class_name', 'teacher_name',
                      'overall_literacy_score', 'risk_level', 'assessment_period']].copy()
        roster.columns = ['Student', 'Grade', 'Class', 'Teacher',
                          'Score', 'Support Need', 'Last Period']
        roster['Score'] = roster['Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
        roster['Support Need'] = roster['Support Need'].apply(_support_label)
        roster = roster.sort_values(['Student', 'Grade'])

        styled_roster = roster.style.map(_color_support, subset=['Support Need'])
        st.dataframe(styled_roster, use_container_width=True, height=400)

        st.download_button('Download Student Roster (CSV)',
                           roster.to_csv(index=False),
                           f"student_roster_{selected_year if selected_year != 'All' else 'all'}.csv",
                           'text/csv')
    else:
        st.info("No students found with the selected filters.")

    # ── Detailed Analytics (collapsible) ──────────────────────────────────
    st.markdown("")
    with st.expander("Detailed Analytics", expanded=False):

        da1, da2 = st.columns(2)

        with da1:
            # Support level trends by year
            if not df.empty and 'risk_level' in df.columns:
                conn = get_db_connection()
                trend_q = '''
                    SELECT school_year, risk_level, COUNT(*) as count
                    FROM (
                        SELECT ls.student_id, ls.school_year, ls.risk_level,
                               ROW_NUMBER() OVER (PARTITION BY ls.student_id, ls.school_year
                                                  ORDER BY ls.calculated_at DESC) as rn
                        FROM literacy_scores ls
                        JOIN students s ON ls.student_id = s.student_id
                '''
                t_conds, t_params = [], []
                if selected_grades:
                    if len(selected_grades) == 1:
                        t_conds.append('s.grade_level = %s'); t_params.append(selected_grades[0])
                    else:
                        ph = ','.join(['%s'] * len(selected_grades))
                        t_conds.append(f's.grade_level IN ({ph})'); t_params.extend(selected_grades)
                if t_conds:
                    trend_q += ' WHERE ' + ' AND '.join(t_conds)
                trend_q += ') sub WHERE rn = 1 GROUP BY school_year, risk_level ORDER BY school_year'
                trend_df = pd.read_sql_query(trend_q, conn, params=t_params)
                conn.close()

                if not trend_df.empty:
                    fig = go.Figure()
                    for risk, color in [('Low', '#28a745'), ('Medium', '#e67e22'), ('High', '#dc3545')]:
                        rd = trend_df[trend_df['risk_level'] == risk]
                        if not rd.empty:
                            fig.add_trace(go.Scatter(
                                x=rd['school_year'], y=rd['count'],
                                mode='lines+markers', name=_SUPPORT_LABEL.get(risk, risk),
                                line=dict(color=color, width=2), marker=dict(size=8)))
                    fig.update_layout(title='Support Need Trends by Year',
                                      xaxis_title='Year', yaxis_title='Students',
                                      height=320, margin=dict(t=40, b=40),
                                      legend=dict(orientation='h', y=1.12))
                    st.plotly_chart(fig, use_container_width=True)

        with da2:
            # Early warning flags
            conn = get_db_connection()
            hist_q = ("SELECT s.student_id, s.student_name, ls.assessment_period, "
                      "ls.overall_literacy_score, ls.calculated_at "
                      "FROM students s JOIN literacy_scores ls "
                      "ON ls.student_id=s.student_id AND ls.school_year=s.school_year "
                      "WHERE " + where_clause)
            hist_df = pd.read_sql_query(hist_q, conn, params=params)
            conn.close()

            warn_rows = []
            if not hist_df.empty:
                order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
                tmp = hist_df.copy()
                tmp['x'] = tmp['assessment_period'].map(order).fillna(0)
                tmp = tmp.sort_values(['student_id', 'x', 'calculated_at'])
                for _, g in tmp.groupby('student_id'):
                    scores = g['overall_literacy_score'].dropna().tolist()
                    if len(scores) >= 3:
                        flags = []
                        if scores[-1] < scores[-2] < scores[-3]:
                            flags.append('Declining trend')
                        if abs(scores[-1] - scores[-3]) <= 1:
                            flags.append('No progress')
                        if np.std(scores[-3:]) >= 8:
                            flags.append('Inconsistent scores')
                        if flags:
                            warn_rows.append({
                                'Student': g.iloc[-1]['student_name'],
                                'Flags': ', '.join(flags),
                            })
            if warn_rows:
                st.markdown("**Early Warning Flags**")
                st.dataframe(pd.DataFrame(warn_rows), use_container_width=True, height=200)
            else:
                st.info("No early warning flags at this time.")

        # Average score by assessment type (for at-risk students)
        conn = get_db_connection()
        measure_q = ("SELECT a.assessment_type, AVG(a.score_normalized) as avg_score, "
                     "COUNT(*) as entries "
                     "FROM assessments a JOIN students s ON a.student_id=s.student_id "
                     "WHERE " + where_clause + " AND a.score_normalized IS NOT NULL "
                     "GROUP BY a.assessment_type ORDER BY avg_score")
        measure_df = pd.read_sql_query(measure_q, conn, params=params)
        conn.close()

        if not measure_df.empty:
            st.markdown("**Average Score by Assessment Type**")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=measure_df['assessment_type'],
                y=measure_df['avg_score'],
                marker_color='#5b9bd5',
                text=[f"{v:.0f}" for v in measure_df['avg_score']],
                textposition='outside',
            ))
            fig.update_layout(
                xaxis_title='', yaxis_title='Average Score',
                height=300, margin=dict(t=20, b=40),
                yaxis=dict(range=[0, max(measure_df['avg_score'].max() * 1.15, 100)]),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Data Quality (collapsible) ────────────────────────────────────────
    with st.expander("Data Quality", expanded=False):
        dq1, dq2 = st.columns(2)
        latest_update = pd.to_datetime(df['calculated_at'], errors='coerce').max() if not df.empty else None
        with dq1:
            st.metric("Last Updated",
                      latest_update.strftime('%Y-%m-%d %H:%M') if pd.notna(latest_update) else "N/A")
            st.metric("Students Assessed", f"{students_with_scores} of {total_students}")
        with dq2:
            conn = get_db_connection()
            missing_q = ("SELECT s.grade_level as Grade, "
                         "COALESCE(s.class_name,'Unassigned') as Class, "
                         "COUNT(DISTINCT s.student_id) as Missing "
                         "FROM students s LEFT JOIN literacy_scores ls "
                         "ON ls.student_id=s.student_id AND ls.school_year=s.school_year "
                         "WHERE " + where_clause + " AND ls.score_id IS NULL "
                         "GROUP BY s.grade_level, s.class_name ORDER BY s.grade_level")
            missing_df = pd.read_sql_query(missing_q, conn, params=params)
            conn.close()
            if not missing_df.empty:
                st.markdown("**Missing Assessments**")
                st.dataframe(missing_df, use_container_width=True, height=160)
            else:
                st.success("All students have assessment data.")
