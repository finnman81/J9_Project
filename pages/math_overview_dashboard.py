"""
Math Overview Dashboard Page
Clean, scannable layout for teachers and administrators.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from core.database import get_all_students, get_db_connection
from core.math_calculations import determine_math_risk_level
from core.math_benchmarks import (
    get_math_benchmark_status, get_math_support_level, math_benchmark_color,
    math_benchmark_emoji, group_math_students,
)
from core.erb_scoring import (
    ERB_SUBTESTS, ERB_SUBTEST_LABELS, summarize_erb_scores,
    erb_stanine_to_tier, get_erb_independent_norm,
    parse_erb_score_value,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPORT_LABEL = {'High': 'Needs Support', 'Medium': 'Monitor', 'Low': 'On Track'}
_SUPPORT_BG = {
    'Needs Support': ('#f5c6cb', '#721c24'),
    'Monitor':       ('#ffeeba', '#856404'),
    'On Track':      ('#c3e6cb', '#155724'),
}
_TIER_BG = {
    'Core (Tier 1)':      ('#c3e6cb', '#155724'),
    'Strategic (Tier 2)': ('#ffeeba', '#856404'),
    'Intensive (Tier 3)': ('#f5c6cb', '#721c24'),
}


def _support_label(risk: str) -> str:
    return _SUPPORT_LABEL.get(risk, risk or 'N/A')


def _render_colored_table(df: pd.DataFrame, color_cols: dict, max_height: int = 400):
    """Render a DataFrame as an HTML table with colored cells for specific columns."""
    css = """
    <style>
    .colored-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        font-family: "Source Sans Pro", sans-serif;
    }
    .colored-table th {
        background-color: #fafafa;
        border-bottom: 2px solid #e0e0e0;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        color: #333;
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .colored-table td {
        padding: 6px 12px;
        border-bottom: 1px solid #f0f0f0;
        color: #333;
    }
    .colored-table tr:hover td {
        background-color: #f8f9fa !important;
    }
    .colored-table-wrap {
        max-height: HEIGHT_PLACEHOLDERpx;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
    }
    .pill {
        padding: 3px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 13px;
        display: inline-block;
        white-space: nowrap;
    }
    </style>
    """.replace("HEIGHT_PLACEHOLDER", str(max_height))

    html = css + f'<div class="colored-table-wrap"><table class="colored-table"><thead><tr>'
    for col in df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        html += '<tr>'
        for col in df.columns:
            val = str(row[col]) if pd.notna(row[col]) else '--'
            if col in color_cols and val in color_cols[col]:
                bg, fg = color_cols[col][val]
                html += f'<td><span class="pill" style="background-color:{bg};color:{fg};">{val}</span></td>'
            else:
                html += f'<td>{val}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

def show_math_overview_dashboard():
    st.title("Math Dashboard")

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
                   ms.overall_math_score, ms.risk_level, ms.trend,
                   ms.assessment_period, ms.calculated_at
            FROM students s
            LEFT JOIN math_scores ms ON s.student_id = ms.student_id
                AND ms.school_year = s.school_year
                AND ms.score_id = (
                    SELECT score_id FROM math_scores ms2
                    WHERE ms2.student_id = s.student_id AND ms2.school_year = s.school_year
                    ORDER BY ms2.calculated_at DESC LIMIT 1)
            WHERE {where_clause}
            ORDER BY s.student_name, s.grade_level
        '''
    else:
        query = f'''
            SELECT s.student_id, s.student_name, s.grade_level, s.class_name,
                   s.teacher_name, s.school_year,
                   ms.overall_math_score, ms.risk_level, ms.trend,
                   ms.assessment_period, ms.calculated_at
            FROM students s
            LEFT JOIN math_scores ms ON ms.student_id = s.student_id
                AND ms.school_year = s.school_year
                AND ms.score_id = (
                    SELECT score_id FROM math_scores ms2
                    WHERE ms2.student_id = s.student_id AND ms2.school_year = s.school_year
                    ORDER BY ms2.calculated_at DESC LIMIT 1)
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
    avg_score = df['overall_math_score'].mean() if 'overall_math_score' in df.columns else 0
    students_with_scores = len(df[df['overall_math_score'].notna()])
    completion_rate = (students_with_scores / total_students * 100) if total_students > 0 else 0

    # Intervention coverage
    conn = get_db_connection()
    cov_q = '''
        SELECT COUNT(DISTINCT s.student_id) AS covered
        FROM students s
        JOIN math_scores ms ON ms.student_id = s.student_id AND ms.school_year = s.school_year
        JOIN interventions i ON i.student_id = s.student_id AND i.status = 'Active'
        WHERE ms.score_id = (
            SELECT score_id FROM math_scores ms2
            WHERE ms2.student_id = s.student_id AND ms2.school_year = s.school_year
            ORDER BY ms2.calculated_at DESC LIMIT 1)
          AND ms.risk_level IN ('High', 'Medium')
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
        if not df.empty and 'overall_math_score' in df.columns:
            scores = df['overall_math_score'].dropna()
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
                    xaxis_title='Math Score', yaxis_title='Students',
                    height=370, margin=dict(t=40, b=40),
                    xaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig, width='stretch')

    with ch2:
        # Average score by grade
        if not df.empty and 'overall_math_score' in df.columns:
            grade_avg = df.groupby('grade_level')['overall_math_score'].mean().reset_index()
            grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth']
            grade_avg['sort'] = grade_avg['grade_level'].apply(
                lambda g: grade_order.index(g) if g in grade_order else len(grade_order))
            grade_avg = grade_avg.sort_values('sort')

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=grade_avg['grade_level'],
                y=grade_avg['overall_math_score'],
                marker_color='#5b9bd5',
                text=[f"{v:.0f}" for v in grade_avg['overall_math_score']],
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
            st.plotly_chart(fig, width='stretch')

    # ── Support Tiers ─────────────────────────────────────────────────────
    st.markdown("")
    st.subheader("Support Tiers")
    st.caption("Students are grouped into tiers based on benchmark performance. "
               "Core = on track, Strategic = needs targeted help, Intensive = needs significant intervention.")

    if not df.empty:
        grouping_df = group_math_students(df, df)

        if not grouping_df.empty and 'support_level' in grouping_df.columns:
            tier_col = 'support_level'
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
            display_cols += [tier_col, 'weakest_skill']
            display_names += ['Support Tier', 'Focus Area']

            tbl = grouping_df[display_cols].copy()
            tbl.columns = display_names
            tbl['Score'] = tbl['Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
            tbl['Focus Area'] = tbl['Focus Area'].fillna('--')
            tbl = tbl.sort_values(['Support Tier', 'Student'])

            # Build color map for tier columns
            tier_color_map = {}
            tier_color_map['Support Tier'] = _TIER_BG
            st.markdown(_render_colored_table(tbl, tier_color_map, max_height=400),
                        unsafe_allow_html=True)

            st.download_button('Download Grouping Report (CSV)',
                               grouping_df.to_csv(index=False),
                               'math_support_tiers.csv', 'text/csv')

    # ── ERB Math Comparison ────────────────────────────────────────────────
    if not df.empty:
        try:
            conn = get_db_connection()
            cohort_ids = df[['student_id', 'school_year']].drop_duplicates()
            assess_q = '''
                SELECT a.student_id, a.school_year, a.assessment_type, a.score_value,
                       s.grade_level
                FROM assessments a
                JOIN students s ON a.student_id = s.student_id AND a.school_year = s.school_year
                WHERE a.assessment_type = 'ERB_Mathematics' AND a.subject_area = 'Math'
            '''
            assess_erb = pd.read_sql_query(assess_q, conn)
            conn.close()
        except Exception:
            assess_erb = pd.DataFrame()

        if not assess_erb.empty:
            assess_erb = assess_erb.merge(
                cohort_ids, on=['student_id', 'school_year'], how='inner'
            )
            # Parse ERB scores
            rows = []
            for _, row in assess_erb.iterrows():
                parsed = parse_erb_score_value(row.get('score_value', ''))
                if parsed.get('stanine') is not None:
                    rows.append({
                        'grade_level': row['grade_level'],
                        'stanine': parsed['stanine'],
                        'percentile': parsed.get('percentile') or 50,
                    })
            if rows:
                erb_agg = pd.DataFrame(rows)
                our_avg = erb_agg.groupby('grade_level').agg(
                    our_stanine=('stanine', 'mean'),
                    our_percentile=('percentile', 'mean'),
                ).reset_index()
                norm_rows = []
                for _, r in our_avg.iterrows():
                    norm = get_erb_independent_norm(r['grade_level'], 'ERB_Mathematics')
                    norm_rows.append({
                        'Grade': r['grade_level'],
                        'Our Avg (Stanine)': round(r['our_stanine'], 1),
                        'Ind. Avg': norm['avg_stanine'],
                        'Diff': round(r['our_stanine'] - norm['avg_stanine'], 1),
                        'Our Avg (Pct)': round(r['our_percentile'], 0),
                        'Ind. Pct': norm['avg_percentile'],
                        'Diff Pct': round(r['our_percentile'] - norm['avg_percentile'], 0),
                    })
                erb_norms_df = pd.DataFrame(norm_rows)

                st.markdown("")
                st.subheader("ERB Math vs Independent School Averages")
                st.caption("Comparison to ERB Independent Norm (IN): independent school students, same time of year.")

                display_norms = erb_norms_df[[
                    'Grade', 'Our Avg (Stanine)', 'Ind. Avg', 'Diff',
                    'Our Avg (Pct)', 'Ind. Pct', 'Diff Pct'
                ]].copy()
                display_norms['Diff'] = display_norms['Diff'].apply(lambda x: f"{x:+.1f}")
                display_norms['Diff Pct'] = display_norms['Diff Pct'].apply(lambda x: f"{x:+.0f}")
                st.dataframe(display_norms, width='stretch', height=280)

    # ── Student Roster ────────────────────────────────────────────────────
    st.markdown("")
    st.subheader("Student Roster")

    if not df.empty:
        roster = df[['student_name', 'grade_level', 'class_name', 'teacher_name',
                      'overall_math_score', 'risk_level', 'assessment_period']].copy()
        roster.columns = ['Student', 'Grade', 'Class', 'Teacher',
                          'Score', 'Support Need', 'Last Period']
        roster['Score'] = roster['Score'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")
        roster['Support Need'] = roster['Support Need'].apply(_support_label)
        roster = roster.sort_values(['Student', 'Grade'])

        st.markdown(_render_colored_table(
            roster, {'Support Need': _SUPPORT_BG}, max_height=500),
            unsafe_allow_html=True)
        st.markdown("")

        st.download_button('Download Student Roster (CSV)',
                           roster.to_csv(index=False),
                           f"math_student_roster_{selected_year if selected_year != 'All' else 'all'}.csv",
                           'text/csv')
    else:
        st.info("No students found with the selected filters.")
