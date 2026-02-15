"""
Math Overview Dashboard Page
Clean, scannable layout for teachers and administrators.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from core.database import (
    get_all_students, get_db_connection,
    get_all_assessments, get_all_scores, get_all_interventions,
)
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
from core.tier_engine import (
    assign_tiers_bulk, TIER_CORE, TIER_STRATEGIC, TIER_INTENSIVE,
    is_needs_support,
)
from core.priority_engine import compute_priority_students, get_top_priority
from core.data_health import compute_data_health
from core.growth_engine import compute_period_growth, compute_cohort_growth_summary

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

    # ── Load supporting data for new engines ────────────────────────────
    yr_filter = selected_year if selected_year != 'All' else None
    all_assessments = get_all_assessments(subject='Math', school_year=yr_filter)
    all_scores = get_all_scores(subject='Math', school_year=yr_filter)
    all_interventions = get_all_interventions(school_year=yr_filter)

    filtered_students = df[['student_id', 'student_name', 'grade_level',
                            'class_name', 'teacher_name', 'school_year']].drop_duplicates(subset=['student_id'])

    # ── Unified tier assignment ───────────────────────────────────────────
    tiered_df = assign_tiers_bulk(filtered_students, all_scores, None,
                                  subject='Math', school_year=yr_filter)

    # ── Compute KPI values ────────────────────────────────────────────────
    total_students = len(df['student_id'].unique())
    needs_support = int(tiered_df['support_tier'].apply(is_needs_support).sum()) if not tiered_df.empty else 0
    strategic_count = int((tiered_df['support_tier'] == TIER_STRATEGIC).sum()) if not tiered_df.empty else 0
    intensive_count = int((tiered_df['support_tier'] == TIER_INTENSIVE).sum()) if not tiered_df.empty else 0
    avg_score = df['overall_math_score'].mean() if 'overall_math_score' in df.columns else 0
    students_with_scores = len(df[df['overall_math_score'].notna()])
    completion_rate = (students_with_scores / total_students * 100) if total_students > 0 else 0

    # Tier-split intervention coverage
    active_int_ids = set()
    if not all_interventions.empty:
        active_ints = all_interventions[all_interventions['status'] == 'Active']
        active_int_ids = set(active_ints['student_id'].unique())

    strategic_ids = set(tiered_df[tiered_df['support_tier'] == TIER_STRATEGIC]['student_id'])
    intensive_ids = set(tiered_df[tiered_df['support_tier'] == TIER_INTENSIVE]['student_id'])
    strat_covered = len(strategic_ids & active_int_ids)
    int_covered = len(intensive_ids & active_int_ids)
    total_need = strategic_count + intensive_count
    total_covered = strat_covered + int_covered

    # Data health
    health = compute_data_health(filtered_students, all_assessments, all_scores,
                                 subject='Math', school_year=yr_filter)

    # ── KPI Cards ─────────────────────────────────────────────────────────
    st.markdown("")
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    with k1:
        st.metric("Total Students", total_students)
    with k2:
        st.metric("Needs Support", needs_support,
                  help="Strategic + Intensive tiers (unified tier logic)")
    with k3:
        st.metric("Average Score", f"{avg_score:.1f}" if avg_score else "N/A")
    with k4:
        cov_pct = f"{total_covered}/{total_need} ({total_covered/total_need*100:.0f}%)" if total_need else "N/A"
        st.metric("Intervention Coverage", cov_pct)
    with k5:
        st.metric("Assessed", f"{completion_rate:.0f}%")
    with k6:
        st.metric("Median Days Since Assess.",
                  f"{health['median_days_since_assessment']:.0f}" if health['median_days_since_assessment'] is not None else "N/A")
    with k7:
        st.metric("% Overdue (>90d)", f"{health['pct_overdue']:.0f}%")

    # Tier-Split Coverage Detail
    cov1, cov2, cov3 = st.columns(3)
    with cov1:
        st.caption(f"Strategic: {strat_covered}/{strategic_count} covered" if strategic_count else "Strategic: 0")
    with cov2:
        st.caption(f"Intensive: {int_covered}/{intensive_count} covered" if intensive_count else "Intensive: 0")
    with cov3:
        st.caption(f"Overall: {total_covered}/{total_need} covered" if total_need else "Overall: N/A")

    # ── Priority Students Panel ───────────────────────────────────────────
    st.markdown("")
    st.subheader("Priority Students")
    st.caption("Students automatically surfaced based on tier, intervention gaps, declining trends, and assessment staleness.")

    priority_df = compute_priority_students(
        filtered_students, all_scores, all_interventions, all_assessments,
        subject='Math', school_year=yr_filter,
    )
    top_priority = get_top_priority(priority_df, n=15)

    if not top_priority.empty:
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric("Flagged Strategic", int((top_priority['support_tier'] == TIER_STRATEGIC).sum()))
        with pc2:
            st.metric("Flagged Intensive", int((top_priority['support_tier'] == TIER_INTENSIVE).sum()))
        with pc3:
            st.metric("Total Flagged", len(top_priority))

        disp = top_priority[['student_name', 'grade_level', 'support_tier',
                              'has_active_intervention', 'days_since_last_assessment',
                              'growth_trend', 'priority_score', 'priority_reasons']].copy()
        disp.columns = ['Student', 'Grade', 'Tier', 'Has Intervention',
                        'Days Since Assess.', 'Trend', 'Priority Score', 'Reasons']
        disp['Reasons'] = disp['Reasons'].apply(lambda r: '; '.join(r) if isinstance(r, list) else str(r))
        disp['Has Intervention'] = disp['Has Intervention'].map({True: 'Yes', False: 'No'})
        disp['Days Since Assess.'] = disp['Days Since Assess.'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else '--')

        st.markdown(_render_colored_table(disp, {'Tier': _TIER_BG}, max_height=400),
                    unsafe_allow_html=True)
    else:
        st.success("No priority students flagged at this time.")

    # ── Period-Aware Growth Metrics ───────────────────────────────────────
    st.markdown("")
    st.subheader("Growth Metrics")
    gp1, gp2 = st.columns([1, 3])
    with gp1:
        growth_period = st.selectbox("Growth Period", ["Fall → Winter", "Winter → Spring", "Fall → Spring"],
                                      key="math_growth_period")
    period_map = {"Fall → Winter": ("Fall", "Winter"), "Winter → Spring": ("Winter", "Spring"),
                  "Fall → Spring": ("Fall", "Spring")}
    from_p, to_p = period_map[growth_period]
    growth_df = compute_period_growth(all_scores, subject='Math', from_period=from_p,
                                       to_period=to_p, school_year=yr_filter)
    summary = compute_cohort_growth_summary(growth_df)

    with gp2:
        gm1, gm2, gm3, gm4 = st.columns(4)
        with gm1:
            st.metric("Median Growth", f"{summary['median_growth']:+.1f}" if summary['median_growth'] is not None else "N/A")
        with gm2:
            st.metric("% Improving", f"{summary['pct_improving']:.0f}%")
        with gm3:
            st.metric("% Declining", f"{summary['pct_declining']:.0f}%")
        with gm4:
            st.metric("Students w/ Growth Data", summary['n'])

    # ── Data Health Panel (expanded by default for Math) ──────────────────
    with st.expander("Data Health", expanded=True):
        dq1, dq2, dq3 = st.columns(3)
        with dq1:
            st.metric("Students Assessed", f"{health['assessed_count']} of {health['total_students']}")
            st.metric("Assessment Coverage", f"{health['assessed_pct']:.0f}%")
            st.metric("Missing Scores", health['missing_scores_count'])
        with dq2:
            st.metric("Invalid Range Scores", health['invalid_range_count'])
            st.metric("Duplicate Assessments", health['duplicate_count'])
            st.metric("NULL-vs-Zero Issues", health['null_vs_zero_issues'],
                      help="Assessments where normalized score is 0 but raw score is empty/null. "
                           "Math data is especially susceptible to this distortion.")
        with dq3:
            st.metric("Median Days Since Assessment",
                      f"{health['median_days_since_assessment']:.0f}" if health['median_days_since_assessment'] is not None else "N/A")
            st.metric(f"% Overdue (>{health['overdue_threshold_days']}d)", f"{health['pct_overdue']:.0f}%")

        if health['missing_scores_students']:
            st.markdown("**Students Missing Scores:**")
            st.caption(", ".join(health['missing_scores_students'][:30])
                       + ("..." if len(health['missing_scores_students']) > 30 else ""))

        # Math-specific: NULL vs 0 score separation
        if not df.empty and 'overall_math_score' in df.columns:
            zero_scores = int((df['overall_math_score'] == 0).sum())
            no_scores = int(df['overall_math_score'].isna().sum())
            if zero_scores > 0 or no_scores > 0:
                st.warning(
                    f"**Score = 0 vs No Score:** {zero_scores} students have a score of 0. "
                    f"{no_scores} students have no score recorded. "
                    f"Ensure zero scores represent actual performance, not missing data."
                )

    # ── Charts (two-column) ───────────────────────────────────────────────
    st.markdown("")
    ch1, ch2 = st.columns(2)

    with ch1:
        # Score distribution histogram -- separate No Score vs Score=0
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
