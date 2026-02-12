"""
Math Student Detail Page
Clean, focused view of an individual student's math profile.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from core.database import (
    get_all_students, get_db_connection, add_teacher_note, get_teacher_notes,
    upsert_student_goal, get_student_goals
)
from core.math_calculations import calculate_math_trend
from core.math_benchmarks import (
    get_math_benchmark_status, get_math_support_level,
    math_benchmark_color, math_benchmark_emoji,
    MATH_MEASURE_LABELS, MATH_MEASURES_BY_GRADE, GRADE_ALIASES, PERIOD_MAP,
)

# ---------------------------------------------------------------------------
# Shared helpers
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
_BM_STATUS_BG = {
    'Above Benchmark':      ('#c3e6cb', '#155724'),
    'At Benchmark':         ('#c3e6cb', '#155724'),
    'Below Benchmark':      ('#ffeeba', '#856404'),
    'Well Below Benchmark': ('#f5c6cb', '#721c24'),
}


def _pill(text, bg, fg):
    return (f'<span style="padding:3px 10px;border-radius:12px;font-weight:600;'
            f'font-size:13px;background-color:{bg};color:{fg};'
            f'display:inline-block;white-space:nowrap;">{text}</span>')


def _render_colored_table(df, color_cols, max_height=400):
    css = """<style>
    .ct{width:100%;border-collapse:collapse;font-size:14px;font-family:"Source Sans Pro",sans-serif}
    .ct th{background:#fafafa;border-bottom:2px solid #e0e0e0;padding:8px 12px;text-align:left;font-weight:600;color:#333;position:sticky;top:0;z-index:1}
    .ct td{padding:6px 12px;border-bottom:1px solid #f0f0f0;color:#333}
    .ct tr:hover td{background:#f8f9fa!important}
    .ct-wrap{max-height:HEIGHTpx;overflow-y:auto;border:1px solid #e0e0e0;border-radius:6px}
    .pill{padding:3px 10px;border-radius:12px;font-weight:600;font-size:13px;display:inline-block;white-space:nowrap}
    </style>""".replace("HEIGHT", str(max_height))
    html = css + '<div class="ct-wrap"><table class="ct"><thead><tr>'
    for c in df.columns:
        html += f'<th>{c}</th>'
    html += '</tr></thead><tbody>'
    for _, row in df.iterrows():
        html += '<tr>'
        for c in df.columns:
            val = str(row[c]) if pd.notna(row[c]) else '--'
            if c in color_cols and val in color_cols[c]:
                bg, fg = color_cols[c][val]
                html += f'<td><span class="pill" style="background-color:{bg};color:{fg};">{val}</span></td>'
            else:
                html += f'<td>{val}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def show_math_student_detail():
    st.title("Math Student Profile")

    # ── Student selector ──────────────────────────────────────────────────
    students_df = get_all_students()
    if students_df.empty:
        st.warning("No students found. Add students via the Grade Entry page.")
        return

    unique_names = sorted(students_df['student_name'].unique().tolist())
    student_name = st.selectbox("Select Student", unique_names)

    student_records = students_df[students_df['student_name'] == student_name]
    stu_row = student_records.sort_values('school_year').iloc[-1]
    grade_years = student_records[['grade_level', 'school_year', 'class_name', 'teacher_name']].drop_duplicates()
    selected_id = int(stu_row['student_id'])

    available_grades = sorted(grade_years['grade_level'].unique().tolist())
    selected_grades = st.multiselect("Grades", available_grades, default=available_grades)
    if not selected_grades:
        st.warning("Select at least one grade."); return

    # ── Data queries ──────────────────────────────────────────────────────
    conn = get_db_connection()
    all_scores_df = pd.read_sql_query('''
        SELECT ms.score_id, ms.student_id, ms.assessment_period,
               ms.overall_math_score, ms.computation_component, ms.concepts_component,
               ms.number_fluency_component, ms.quantity_discrimination_component,
               ms.risk_level, ms.trend, ms.calculated_at,
               s.grade_level, s.school_year, s.class_name
        FROM math_scores ms
        JOIN students s ON ms.student_id = s.student_id
        WHERE s.student_name = %s
        ORDER BY s.school_year, s.grade_level,
            CASE ms.assessment_period WHEN 'Fall' THEN 1 WHEN 'Winter' THEN 2
            WHEN 'Spring' THEN 3 WHEN 'EOY' THEN 4 ELSE 0 END, ms.calculated_at
    ''', conn, params=[student_name])

    assessments_df = pd.read_sql_query('''
        SELECT a.assessment_id, a.student_id, a.assessment_type, a.assessment_period,
               a.score_value, a.score_normalized, a.assessment_date, a.notes, a.concerns,
               s.grade_level, s.school_year, s.class_name
        FROM assessments a JOIN students s ON a.student_id = s.student_id
        WHERE s.student_name = %s AND a.subject_area = 'Math'
        ORDER BY s.school_year, s.grade_level, a.assessment_date DESC,
            CASE a.assessment_period WHEN 'Fall' THEN 1 WHEN 'Winter' THEN 2
            WHEN 'Spring' THEN 3 WHEN 'EOY' THEN 4 ELSE 0 END
    ''', conn, params=[student_name])

    interventions_df = pd.read_sql_query('''
        SELECT i.*, s.student_name, s.grade_level, s.school_year
        FROM interventions i JOIN students s ON i.student_id = s.student_id
        WHERE s.student_name = %s ORDER BY i.start_date DESC
    ''', conn, params=[student_name])
    conn.close()

    # Filter by selected grades
    if not all_scores_df.empty:
        all_scores_df = all_scores_df[all_scores_df['grade_level'].isin(selected_grades)].drop_duplicates().reset_index(drop=True)
    if not assessments_df.empty:
        assessments_df = assessments_df[assessments_df['grade_level'].isin(selected_grades)].drop_duplicates().reset_index(drop=True)
    if not interventions_df.empty:
        interventions_df = interventions_df[interventions_df['grade_level'].isin(selected_grades)].drop_duplicates().reset_index(drop=True)

    # Latest score
    latest_score = None
    bm_status = None
    if not all_scores_df.empty:
        pk = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        tmp = all_scores_df.copy()
        tmp['yk'] = tmp['school_year'].apply(lambda v: int(str(v).split('-')[0]) if str(v).split('-')[0].isdigit() else 0)
        tmp['pk'] = tmp['assessment_period'].map(pk).fillna(0)
        tmp = tmp.sort_values(['yk', 'pk', 'calculated_at'])
        latest_score = tmp.iloc[-1].to_dict()

    # Trend computation
    if latest_score and latest_score.get('trend') in ('Unknown', None, 'New'):
        scores_vals = all_scores_df[all_scores_df['overall_math_score'].notna()]
        if len(scores_vals) >= 2:
            last2 = scores_vals.tail(2)
            prev_s = last2.iloc[0]['overall_math_score']
            curr_s = last2.iloc[1]['overall_math_score']
            if prev_s is not None and curr_s is not None:
                latest_score['trend'] = calculate_math_trend(curr_s, prev_s)

    active_interventions = interventions_df[interventions_df['status'] == 'Active'] if not interventions_df.empty else pd.DataFrame()

    # ── Student Info Card + KPIs ──────────────────────────────────────────
    st.markdown("")
    overall_score = latest_score.get('overall_math_score', 0) if latest_score else 0
    risk_level = latest_score.get('risk_level', 'Unknown') if latest_score else 'Unknown'
    trend = latest_score.get('trend', 'Unknown') if latest_score else 'Unknown'
    support_label = _SUPPORT_LABEL.get(risk_level, risk_level)

    if latest_score:
        if overall_score >= 70:
            bm_status = 'At Benchmark'
        elif overall_score >= 50:
            bm_status = 'Below Benchmark'
        else:
            bm_status = 'Well Below Benchmark'
        support_tier = get_math_support_level(bm_status)
    else:
        support_tier = 'Unknown'

    latest_class = grade_years['class_name'].dropna().iloc[-1] if not grade_years['class_name'].dropna().empty else 'N/A'
    latest_teacher = grade_years['teacher_name'].dropna().iloc[-1] if not grade_years['teacher_name'].dropna().empty else 'N/A'
    latest_grade_display = selected_grades[-1] if selected_grades else 'N/A'

    i1, i2, i3, i4 = st.columns(4)
    with i1:
        st.metric("Student", student_name)
    with i2:
        st.metric("Grade / Class", f"{latest_grade_display} / {latest_class}")
    with i3:
        st.metric("Teacher", latest_teacher)
    with i4:
        years_tracked = len(grade_years)
        st.metric("Years Tracked", years_tracked)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Score", f"{overall_score:.0f}" if overall_score else "--")
    with k2:
        bg, fg = _SUPPORT_BG.get(support_label, ('#e0e0e0', '#333'))
        st.markdown(f"**Support Need**<br>{_pill(support_label, bg, fg)}", unsafe_allow_html=True)
    with k3:
        trend_icon = {'Improving': '📈', 'Declining': '📉', 'Stable': '➡️'}.get(trend, '')
        st.metric("Trend", f"{trend_icon} {trend}")
    with k4:
        st.metric("Support Tier", support_tier)
    with k5:
        st.metric("Interventions", len(active_interventions))

    # ── Progress Chart ─────────────────────────────────────────────────────
    st.markdown("")
    if not all_scores_df.empty:
        pk = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        dedupe_df = all_scores_df.copy()
        dedupe_df['_yk'] = dedupe_df['school_year'].apply(
            lambda v: int(str(v).split('-')[0]) if str(v).split('-')[0].isdigit() else 0
        )
        dedupe_df['_pk'] = dedupe_df['assessment_period'].map(pk).fillna(0)
        dedupe_df = dedupe_df.sort_values(['_yk', '_pk', 'calculated_at'])
        scores_df = dedupe_df.drop_duplicates(
            subset=['grade_level', 'assessment_period'], keep='last'
        ).reset_index(drop=True)
        scores_df['period_label'] = scores_df['grade_level'] + ' - ' + scores_df['assessment_period']
        grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth']
        scores_df['_gord'] = scores_df['grade_level'].apply(
            lambda g: grade_order.index(g) if g in grade_order else 99
        )
        scores_df = scores_df.sort_values(['_gord', '_pk']).reset_index(drop=True)

        ch1, ch2 = st.columns([3, 2])
        with ch1:
            fig = go.Figure()
            fig.add_hrect(y0=70, y1=100, fillcolor="#28a745", opacity=0.07, line_width=0,
                          annotation_text="On Track", annotation_position="top right")
            fig.add_hrect(y0=50, y1=70, fillcolor="#ffc107", opacity=0.07, line_width=0,
                          annotation_text="Monitor", annotation_position="top right")
            fig.add_hrect(y0=0, y1=50, fillcolor="#dc3545", opacity=0.07, line_width=0,
                          annotation_text="Needs Support", annotation_position="top right")
            fig.add_trace(go.Scatter(
                x=scores_df['period_label'], y=scores_df['overall_math_score'],
                mode='lines+markers', name='Score',
                line=dict(color='#5b9bd5', width=3), marker=dict(size=10)))
            fig.update_layout(title='Math Progress Over Time', xaxis_title='',
                              yaxis_title='Score', height=380,
                              yaxis=dict(range=[0, 100]), xaxis=dict(tickangle=45),
                              margin=dict(t=40, b=60))
            st.plotly_chart(fig, width='stretch')

        with ch2:
            st.markdown("**Strengths & Areas for Growth**")
            areas = {}
            if latest_score:
                for comp, label in [('computation_component', 'Computation'),
                                     ('concepts_component', 'Concepts & Application'),
                                     ('number_fluency_component', 'Number Fluency'),
                                     ('quantity_discrimination_component', 'Quantity Discrimination')]:
                    val = latest_score.get(comp)
                    if val is not None and pd.notna(val):
                        areas[label] = float(val)

            if areas:
                sorted_areas = sorted(areas.items(), key=lambda x: x[1], reverse=True)
                strengths = [(n, s) for n, s in sorted_areas if s >= 60][:2]
                growth = [(n, s) for n, s in sorted_areas if s < 60]
                growth = sorted(growth, key=lambda x: x[1])[:2] if growth else []

                st.markdown("**Top Strengths**")
                if strengths:
                    for name, score in strengths:
                        st.markdown(f"&nbsp;&nbsp; ✅ **{name}** — {score:.0f}")
                else:
                    st.caption("No areas at benchmark yet.")

                st.markdown("**Areas for Growth**")
                if growth:
                    for name, score in growth:
                        st.markdown(f"&nbsp;&nbsp; 🔶 **{name}** — {score:.0f}")
                else:
                    st.caption("No areas below benchmark.")

    # ── Acadience Math Measures ────────────────────────────────────────────
    if not assessments_df.empty and latest_score:
        g_alias = GRADE_ALIASES.get(latest_score.get('grade_level', ''), '')
        grade_measures = MATH_MEASURES_BY_GRADE.get(g_alias, [])
        p_alias = PERIOD_MAP.get(latest_score.get('assessment_period', ''), '')

        acad_rows = []
        for m in grade_measures:
            m_df = assessments_df[assessments_df['assessment_type'] == m]
            if not m_df.empty:
                latest_m = m_df.iloc[-1]
                raw = latest_m.get('score_value', '--')
                norm = latest_m.get('score_normalized')
                try:
                    raw_float = float(raw)
                except (ValueError, TypeError):
                    raw_float = norm
                bm = get_math_benchmark_status(m, latest_score['grade_level'],
                                          latest_score['assessment_period'], raw_float) if raw_float else None
                bm_text = bm or 'N/A'
                tier = get_math_support_level(bm) if bm else 'N/A'
                acad_rows.append({
                    'Measure': MATH_MEASURE_LABELS.get(m, m),
                    'Raw Score': raw,
                    'Benchmark': bm_text,
                    'Tier': tier,
                })

        if acad_rows:
            st.markdown("")
            st.subheader("Acadience Math Measures")
            st.caption(f"Grade-appropriate measures for {latest_score['grade_level']} "
                       f"({latest_score['assessment_period']})")
            acad_df = pd.DataFrame(acad_rows)
            st.markdown(_render_colored_table(acad_df, {
                'Benchmark': _BM_STATUS_BG,
                'Tier': _TIER_BG,
            }, max_height=250), unsafe_allow_html=True)

    # ── Assessment History ─────────────────────────────────────────────────
    with st.expander("Assessment History", expanded=False):
        if not assessments_df.empty:
            disp_a = assessments_df[['grade_level', 'school_year', 'assessment_type',
                'assessment_period', 'score_value', 'score_normalized']].copy()
            disp_a.columns = ['Grade', 'Year', 'Type', 'Period', 'Score', 'Normalized']
            disp_a['Normalized'] = disp_a['Normalized'].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "--")
            st.dataframe(disp_a, width='stretch', height=300)
        else:
            st.info("No math assessments recorded.")
