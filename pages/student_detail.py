"""
Student Detail Page
Clean, focused view of an individual student's literacy profile.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from database import (
    get_all_students, get_db_connection, add_teacher_note, get_teacher_notes,
    upsert_student_goal, get_student_goals
)
from calculations import calculate_component_scores, calculate_trend
from benchmarks import (
    get_benchmark_status, get_support_level,
    benchmark_color, benchmark_emoji,
    generate_parent_report_html, MEASURE_LABELS,
    MEASURES_BY_GRADE, GRADE_ALIASES, PERIOD_MAP,
)
from erb_scoring import (
    ERB_SUBTESTS, ERB_SUBTEST_LABELS, ERB_SUBTEST_DESCRIPTIONS,
    summarize_erb_scores, get_erb_independent_norm,
    classify_stanine, stanine_color, stanine_emoji,
    classify_percentile, percentile_color,
    classify_growth_percentile, growth_percentile_color,
    erb_stanine_to_tier, get_latest_erb_tier, blend_tiers,
)

# ---------------------------------------------------------------------------
# Shared helpers (same style as overview dashboard)
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
_GROWTH_BG = {
    'Strong Growth':   ('#c3e6cb', '#155724'),
    'Moderate Growth': ('#d1ecf1', '#0c5460'),
    'Minimal Growth':  ('#ffeeba', '#856404'),
    'Decline':         ('#f5c6cb', '#721c24'),
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

def show_student_detail():
    st.title("Student Profile")

    # ── Student selector ──────────────────────────────────────────────────
    students_df = get_all_students()
    if students_df.empty:
        st.warning("No students found. Add students via the Grade Entry page.")
        return

    # Unique student names for a clean dropdown
    unique_names = sorted(students_df['student_name'].unique().tolist())

    student_name = st.selectbox("Select Student", unique_names)

    student_records = students_df[students_df['student_name'] == student_name]
    # Pick the most-recent record as the "primary" row (latest school year)
    stu_row = student_records.sort_values('school_year').iloc[-1]
    grade_years = student_records[['grade_level', 'school_year', 'class_name', 'teacher_name']].drop_duplicates()
    selected_id = int(stu_row['student_id'])

    # Grade filter (compact)
    available_grades = sorted(grade_years['grade_level'].unique().tolist())
    selected_grades = st.multiselect("Grades", available_grades, default=available_grades)
    if not selected_grades:
        st.warning("Select at least one grade."); return

    # ── Data queries ──────────────────────────────────────────────────────
    conn = get_db_connection()
    all_scores_df = pd.read_sql_query('''
        SELECT ls.score_id, ls.student_id, ls.assessment_period,
               ls.overall_literacy_score, ls.reading_component, ls.phonics_component,
               ls.spelling_component, ls.sight_words_component,
               ls.risk_level, ls.trend, ls.calculated_at,
               s.grade_level, s.school_year, s.class_name
        FROM literacy_scores ls
        JOIN students s ON ls.student_id = s.student_id
        WHERE s.student_name = %s
        ORDER BY s.school_year, s.grade_level,
            CASE ls.assessment_period WHEN 'Fall' THEN 1 WHEN 'Winter' THEN 2
            WHEN 'Spring' THEN 3 WHEN 'EOY' THEN 4 ELSE 0 END, ls.calculated_at
    ''', conn, params=[student_name])

    assessments_df = pd.read_sql_query('''
        SELECT a.assessment_id, a.student_id, a.assessment_type, a.assessment_period,
               a.score_value, a.score_normalized, a.assessment_date, a.notes, a.concerns,
               s.grade_level, s.school_year, s.class_name
        FROM assessments a JOIN students s ON a.student_id = s.student_id
        WHERE s.student_name = %s
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
        scores_vals = all_scores_df[all_scores_df['overall_literacy_score'].notna()]
        if len(scores_vals) >= 2:
            last2 = scores_vals.tail(2)
            prev_s = last2.iloc[0]['overall_literacy_score']
            curr_s = last2.iloc[1]['overall_literacy_score']
            if prev_s is not None and curr_s is not None:
                latest_score['trend'] = calculate_trend(curr_s, prev_s)

    active_interventions = interventions_df[interventions_df['status'] == 'Active'] if not interventions_df.empty else pd.DataFrame()

    # ── Student Info Card + KPIs ──────────────────────────────────────────
    st.markdown("")
    overall_score = latest_score.get('overall_literacy_score', 0) if latest_score else 0
    risk_level = latest_score.get('risk_level', 'Unknown') if latest_score else 'Unknown'
    trend = latest_score.get('trend', 'Unknown') if latest_score else 'Unknown'
    support_label = _SUPPORT_LABEL.get(risk_level, risk_level)

    if latest_score:
        # Use internal 0-100 thresholds (overall_literacy_score is normalized, NOT raw Acadience)
        if overall_score >= 70:
            bm_status = 'At Benchmark'
        elif overall_score >= 50:
            bm_status = 'Below Benchmark'
        else:
            bm_status = 'Well Below Benchmark'
        support_tier = get_support_level(bm_status)
    else:
        support_tier = 'Unknown'

    # Compact info row
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

    # KPI row with support pill
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

    # Class comparison metrics (compact, no chart)
    if latest_score and latest_class != 'N/A':
        conn = get_db_connection()
        cdf = pd.read_sql_query('''
            SELECT AVG(ls.overall_literacy_score) as avg
            FROM literacy_scores ls JOIN students s ON ls.student_id = s.student_id
            WHERE s.class_name = %s AND s.school_year = %s
              AND ls.score_id = (SELECT score_id FROM literacy_scores ls2
                  WHERE ls2.student_id = s.student_id AND ls2.school_year = s.school_year
                  ORDER BY ls2.calculated_at DESC LIMIT 1)
        ''', conn, params=[latest_class, stu_row['school_year']])
        conn.close()
        if not cdf.empty and cdf.iloc[0]['avg'] is not None:
            class_avg = cdf.iloc[0]['avg']
            diff = overall_score - class_avg
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.metric("Class Average", f"{class_avg:.0f}")
            with cc2:
                st.metric("This Student", f"{overall_score:.0f}")
            with cc3:
                st.metric("vs Class", f"{diff:+.0f}", delta=f"{diff:+.0f}")

    # ── Progress Chart + Strengths/Weaknesses ─────────────────────────────
    st.markdown("")
    if not all_scores_df.empty:
        # One point per (grade, period): keep latest school_year to avoid duplicate x and two lines
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
                x=scores_df['period_label'], y=scores_df['overall_literacy_score'],
                mode='lines+markers', name='Score',
                line=dict(color='#5b9bd5', width=3), marker=dict(size=10)))
            fig.update_layout(title='Progress Over Time', xaxis_title='',
                              yaxis_title='Score', height=380,
                              yaxis=dict(range=[0, 100]), xaxis=dict(tickangle=45),
                              margin=dict(t=40, b=60))
            st.plotly_chart(fig, width='stretch')

        with ch2:
            # Strengths & Weaknesses
            st.markdown("**Strengths & Areas for Growth**")
            areas = {}
            if latest_score:
                for comp, label in [('reading_component', 'Reading'),
                                     ('phonics_component', 'Phonics'),
                                     ('sight_words_component', 'Sight Words')]:
                    val = latest_score.get(comp)
                    if val is not None and pd.notna(val):
                        areas[label] = float(val)

            # Add Acadience measure scores
            if not assessments_df.empty and latest_score:
                g_alias = GRADE_ALIASES.get(latest_score.get('grade_level', ''))
                grade_measures = MEASURES_BY_GRADE.get(g_alias, [])
                for m in grade_measures:
                    m_df = assessments_df[assessments_df['assessment_type'] == m]
                    if not m_df.empty:
                        val = m_df.iloc[-1].get('score_normalized')
                        if val is not None and pd.notna(val):
                            areas[MEASURE_LABELS.get(m, m)] = float(val)

            if areas:
                sorted_areas = sorted(areas.items(), key=lambda x: x[1], reverse=True)
                # Strengths = scores at or above 60; growth = below 60 (avoid labeling low scores as strengths)
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

                if support_tier and 'Intensive' in support_tier and growth:
                    st.info(f"Recommendation: Focus intervention on **{growth[0][0]}** (lowest at {growth[0][1]:.0f})")
                elif support_tier and 'Strategic' in support_tier and growth:
                    st.info(f"Recommendation: Targeted practice in **{growth[0][0]}**")
            else:
                st.caption("No component data available yet.")

    # ── Acadience Measures ────────────────────────────────────────────────
    if not assessments_df.empty and latest_score:
        g_alias = GRADE_ALIASES.get(latest_score.get('grade_level', ''), '')
        grade_measures = MEASURES_BY_GRADE.get(g_alias, [])
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
                bm = get_benchmark_status(m, latest_score['grade_level'],
                                          latest_score['assessment_period'], raw_float) if raw_float else None
                bm_text = bm or 'N/A'
                tier = get_support_level(bm) if bm else 'N/A'
                acad_rows.append({
                    'Measure': MEASURE_LABELS.get(m, m),
                    'Raw Score': raw,
                    'Benchmark': bm_text,
                    'Tier': tier,
                })

        if acad_rows:
            st.markdown("")
            st.subheader("Acadience Measures")
            st.caption(f"Grade-appropriate measures for {latest_score['grade_level']} "
                       f"({latest_score['assessment_period']})")
            acad_df = pd.DataFrame(acad_rows)
            st.markdown(_render_colored_table(acad_df, {
                'Benchmark': _BM_STATUS_BG,
                'Tier': _TIER_BG,
            }, max_height=250), unsafe_allow_html=True)

    # ── ERB / CTP5 Scores ────────────────────────────────────────────────
    erb_summaries = summarize_erb_scores(assessments_df, student_name) if not assessments_df.empty else []
    if erb_summaries:
        st.markdown("")
        st.subheader("ERB / CTP5 Scores")
        st.caption("Norm-referenced scores from the Comprehensive Testing Program (CTP5). "
                   "Comparison to ERB Independent Norm (IN): independent school averages, same time of year.")

        erb_latest = {}
        for s in erb_summaries:
            erb_latest[s['subtest']] = s

        # Compact summary table with Independent Norm comparison
        erb_tbl_rows = []
        for s in erb_summaries:
            grade_level = s.get('grade_level') or (latest_score.get('grade_level') if latest_score else '')
            norm = get_erb_independent_norm(grade_level, s['subtest'])
            ind_stanine = norm['avg_stanine']
            ind_pct = norm['avg_percentile']
            stu_stanine = s['stanine']
            stu_pct = s.get('percentile')
            diff_s = (stu_stanine - ind_stanine) if stu_stanine is not None else None
            diff_p = (stu_pct - ind_pct) if stu_pct is not None else None
            vs_ind = '--'
            if diff_s is not None:
                vs_ind = f"{diff_s:+.1f}" if diff_s != 0 else "At"
            erb_tbl_rows.append({
                'Subtest': s['label'],
                'Stanine': f"{stanine_emoji(s['stanine'])} {s['stanine']}" if s['stanine'] else '--',
                'Ind. Avg': f"{ind_stanine:.1f}",
                'vs Ind. Avg': vs_ind,
                'Percentile': f"{int(s['percentile'])}th" if s['percentile'] else '--',
                'Growth %ile': f"{int(s['growth_percentile'])}" if s['growth_percentile'] else '--',
                'Tier': s['tier'],
            })
        erb_tbl = pd.DataFrame(erb_tbl_rows)
        st.markdown(_render_colored_table(erb_tbl, {'Tier': _TIER_BG}, max_height=280),
                    unsafe_allow_html=True)

        # Charts in expander (with Independent Norm reference)
        with st.expander("ERB Charts", expanded=False):
            ec1, ec2 = st.columns(2)
            with ec1:
                labels = [erb_latest[k]['label'] for k in erb_latest]
                stanines = [erb_latest[k]['stanine'] or 0 for k in erb_latest]
                # Independent norm ref (use first summary's grade for single ref line)
                ref_grade = erb_summaries[0].get('grade_level') if erb_summaries else ''
                ref_subtest = erb_summaries[0]['subtest'] if erb_summaries else ''
                ind_norm = get_erb_independent_norm(ref_grade, ref_subtest)
                ind_stanine_line = ind_norm['avg_stanine']
                fig_s = go.Figure()
                fig_s.add_trace(go.Bar(x=labels, y=stanines,
                    marker_color=[stanine_color(s) for s in stanines],
                    text=[str(s) for s in stanines], textposition='auto', name='Student'))
                fig_s.add_hline(y=ind_stanine_line, line_dash="dash", line_color="#6c757d",
                                annotation_text="Ind. school avg", annotation_position="right")
                fig_s.add_hrect(y0=0, y1=3.5, fillcolor="#dc3545", opacity=0.06, line_width=0)
                fig_s.add_hrect(y0=3.5, y1=6.5, fillcolor="#ffc107", opacity=0.06, line_width=0)
                fig_s.add_hrect(y0=6.5, y1=9.5, fillcolor="#28a745", opacity=0.06, line_width=0)
                fig_s.update_layout(title='Stanine Scores', yaxis=dict(range=[0, 9.5], dtick=1),
                                    height=320, xaxis=dict(tickangle=30), margin=dict(t=40, b=60))
                st.plotly_chart(fig_s, width='stretch')

            with ec2:
                pcts = [erb_latest[k].get('percentile') or 0 for k in erb_latest]
                ind_pct_line = ind_norm['avg_percentile']
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(x=labels, y=pcts,
                    marker_color=[percentile_color(p) for p in pcts],
                    text=[f"{int(p)}th" for p in pcts], textposition='auto', name='Student'))
                fig_p.add_hline(y=ind_pct_line, line_dash="dash", line_color="#6c757d",
                                annotation_text="Ind. school avg", annotation_position="right")
                fig_p.update_layout(title='Percentile Ranks', yaxis=dict(range=[0, 100]),
                                    height=320, xaxis=dict(tickangle=30), margin=dict(t=40, b=60))
                st.plotly_chart(fig_p, width='stretch')

    # ── Growth & Component Analysis (expander) ────────────────────────────
    st.markdown("")
    with st.expander("Growth & Component Analysis", expanded=False):
        # Growth rate: within (grade, school_year) only so we get Fall->Winter->Spring, never Fall->Fall
        if not all_scores_df.empty and len(all_scores_df) >= 2:
            p_order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
            g_rows = []
            for (gv, sy), grp in all_scores_df.groupby(['grade_level', 'school_year']):
                gs = grp.copy()
                gs['po'] = gs['assessment_period'].map(p_order).fillna(0)
                gs = gs.sort_values('po').drop_duplicates(subset=['assessment_period'], keep='last')
                for i in range(1, len(gs)):
                    prev, curr = gs.iloc[i - 1], gs.iloc[i]
                    ps, cs = prev.get('overall_literacy_score'), curr.get('overall_literacy_score')
                    if ps is not None and cs is not None and pd.notna(ps) and pd.notna(cs):
                        growth = cs - ps
                        if growth >= 10:
                            rate = 'Strong Growth'
                        elif growth >= 3:
                            rate = 'Moderate Growth'
                        elif growth >= 0:
                            rate = 'Minimal Growth'
                        else:
                            rate = 'Decline'
                        g_rows.append({
                            'Grade': gv,
                            'Year': str(sy),
                            'From': prev['assessment_period'],
                            'To': curr['assessment_period'],
                            'Start': f"{ps:.0f}", 'End': f"{cs:.0f}",
                            'Growth': f"{growth:+.0f}",
                            'Rate': rate,
                        })
            if g_rows:
                st.markdown("**Growth Rate Classification**")
                gdf = pd.DataFrame(g_rows)
                st.markdown(_render_colored_table(gdf, {'Rate': _GROWTH_BG}, max_height=240),
                            unsafe_allow_html=True)

        # Component scores over time (same dedupe: one point per grade-period)
        if not all_scores_df.empty and len(all_scores_df) > 1:
            pk = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
            comp_df = all_scores_df.copy()
            comp_df['_yk'] = comp_df['school_year'].apply(
                lambda v: int(str(v).split('-')[0]) if str(v).split('-')[0].isdigit() else 0
            )
            comp_df['_pk'] = comp_df['assessment_period'].map(pk).fillna(0)
            comp_df = comp_df.sort_values(['_yk', '_pk', 'calculated_at'])
            comp_df = comp_df.drop_duplicates(
                subset=['grade_level', 'assessment_period'], keep='last'
            ).reset_index(drop=True)
            comp_df['period_label'] = comp_df['grade_level'] + ' - ' + comp_df['assessment_period']
            grade_order = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth']
            comp_df['_gord'] = comp_df['grade_level'].apply(
                lambda g: grade_order.index(g) if g in grade_order else 99
            )
            comp_df = comp_df.sort_values(['_gord', '_pk']).reset_index(drop=True)
            fig_c = go.Figure()
            for col, name, color in [('reading_component', 'Reading', '#5b9bd5'),
                                      ('phonics_component', 'Phonics', '#28a745'),
                                      ('sight_words_component', 'Sight Words', '#e67e22')]:
                if comp_df[col].notna().any():
                    fig_c.add_trace(go.Scatter(x=comp_df['period_label'], y=comp_df[col],
                        mode='lines+markers', name=name, line=dict(color=color, width=2)))
            fig_c.update_layout(title='Component Scores Over Time', yaxis=dict(range=[0, 100]),
                                height=320, xaxis=dict(tickangle=45), margin=dict(t=40, b=60),
                                legend=dict(orientation='h', y=1.12))
            st.plotly_chart(fig_c, width='stretch')

    # ── Interventions & Goals (expander) ──────────────────────────────────
    with st.expander("Interventions & Goals", expanded=False):
        if not interventions_df.empty:
            st.markdown("**Active Interventions**")
            disp_int = interventions_df[['intervention_type', 'status', 'frequency',
                                         'duration_minutes', 'start_date', 'notes']].copy()
            disp_int.columns = ['Type', 'Status', 'Frequency', 'Minutes', 'Start', 'Notes']
            disp_int['Notes'] = disp_int['Notes'].fillna('--')
            st.dataframe(disp_int, width='stretch', height=180)
        else:
            st.info("No interventions recorded.")

        st.markdown("**Set a Goal**")
        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            goal_measure = st.selectbox('Measure',
                ['Composite', 'ORF', 'NWF-CLS', 'reading_component', 'phonics_component', 'sight_words_component'])
        with gc2:
            baseline = st.number_input('Baseline', min_value=0.0, max_value=200.0, step=0.1)
        with gc3:
            target = st.number_input('Target', min_value=0.0, max_value=200.0, step=0.1, value=70.0)
        with gc4:
            weekly_growth = st.number_input('Weekly Growth', min_value=0.0, step=0.1, value=0.8)
        gd1, gd2 = st.columns(2)
        with gd1:
            goal_start = st.date_input('Start Date', key='goal_start')
        with gd2:
            goal_target_date = st.date_input('Target Date', key='goal_target')
        if st.button('Save Goal') and selected_id:
            upsert_student_goal(selected_id, goal_measure, baseline, target,
                                weekly_growth, goal_start.strftime('%Y-%m-%d'),
                                goal_target_date.strftime('%Y-%m-%d'))
            st.success('Goal saved.')
            st.rerun()

        # Show existing goals
        if not student_records.empty:
            gframes = [get_student_goals(sid) for sid in student_records['student_id'].tolist()]
            gframes = [g for g in gframes if not g.empty]
            if gframes:
                goals_df = pd.concat(gframes, ignore_index=True)
                st.markdown("**Current Goals**")
                st.dataframe(goals_df[['measure', 'baseline_score', 'target_score',
                    'expected_weekly_growth', 'start_date', 'target_date']],
                    width='stretch', height=160)

    # ── Teacher Notes (expander) ──────────────────────────────────────────
    with st.expander("Teacher Notes", expanded=False):
        nc1, nc2, nc3 = st.columns([1, 1, 2])
        with nc1:
            note_tag = st.selectbox('Tag', ['Attendance', 'Behavior', 'Comprehension',
                                             'Decoding', 'Home Reading', 'Progress', 'Other'])
        with nc2:
            note_date = st.date_input('Date', key='note_date')
        with nc3:
            note_text = st.text_input('Note')
        if st.button('Save Note') and note_text.strip() and selected_id:
            add_teacher_note(selected_id, note_text.strip(), note_tag, note_date.strftime('%Y-%m-%d'))
            st.success('Note saved.')
            st.rerun()

        # Show existing notes
        nframes = [get_teacher_notes(sid) for sid in student_records['student_id'].tolist()]
        nframes = [n for n in nframes if not n.empty]
        if nframes:
            all_notes = pd.concat(nframes, ignore_index=True)
            disp_notes = all_notes[['note_date', 'tag', 'note_text', 'created_by']].copy()
            disp_notes.columns = ['Date', 'Tag', 'Note', 'By']
            st.dataframe(disp_notes, width='stretch', height=200)
        else:
            all_notes = pd.DataFrame()

    # ── Assessment History (expander) ─────────────────────────────────────
    with st.expander("Assessment History", expanded=False):
        if not assessments_df.empty:
            disp_a = assessments_df[['grade_level', 'school_year', 'assessment_type',
                'assessment_period', 'score_value', 'score_normalized']].copy()
            disp_a.columns = ['Grade', 'Year', 'Type', 'Period', 'Score', 'Normalized']
            disp_a['Normalized'] = disp_a['Normalized'].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "--")
            st.dataframe(disp_a, width='stretch', height=300)
        else:
            st.info("No assessments recorded.")

    # ── Downloads ─────────────────────────────────────────────────────────
    st.markdown("")
    dl1, dl2 = st.columns(2)
    with dl1:
        if latest_score:
            components_dict = {
                'reading_component': latest_score.get('reading_component'),
                'phonics_component': latest_score.get('phonics_component'),
                'spelling_component': latest_score.get('spelling_component'),
                'sight_words_component': latest_score.get('sight_words_component'),
            }
            inv_list = [r.to_dict() for _, r in interventions_df.head(5).iterrows()] if not interventions_df.empty else []
            goal_list = []
            for sid in student_records['student_id'].tolist():
                gf = get_student_goals(sid)
                if not gf.empty:
                    goal_list.extend([gr.to_dict() for _, gr in gf.iterrows()])

            erb_report = None
            if erb_summaries:
                erb_report = []
                seen = set()
                for es in reversed(erb_summaries):
                    if es['subtest'] not in seen:
                        seen.add(es['subtest'])
                        erb_report.append({
                            'label': es['label'], 'stanine': es['stanine'],
                            'percentile': es.get('percentile'),
                            'classification': es.get('classification', ''),
                            'description': ERB_SUBTEST_DESCRIPTIONS.get(es['subtest'], ''),
                        })
                erb_report.reverse()

            html = generate_parent_report_html(
                student_name=student_name,
                grade=stu_row.get('grade_level', ''),
                teacher=stu_row.get('teacher_name', ''),
                school_year=stu_row.get('school_year', ''),
                period=latest_score.get('assessment_period', ''),
                overall_score=overall_score,
                risk_level=risk_level,
                components=components_dict,
                interventions=inv_list,
                goals=goal_list or None,
                benchmark_status=bm_status,
                erb_scores=erb_report,
            )
            st.download_button('Parent Report (HTML)', html.encode('utf-8'),
                f"{student_name.lower().replace(' ','_')}_report.html", 'text/html')

    with dl2:
        if latest_score:
            parts = [
                "<html><head><style>body{font-family:Arial;margin:2em}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;text-align:left}th{background:#f5f5f5}</style></head><body>",
                f"<h1>Intervention Plan — {student_name}</h1>",
                f"<p><b>Score:</b> {overall_score:.0f} | <b>Support Need:</b> {support_label}</p>",
                "<h2>Interventions</h2>",
            ]
            if not interventions_df.empty:
                parts.append("<table><tr><th>Type</th><th>Status</th><th>Frequency</th><th>Start</th></tr>")
                for _, r in interventions_df.head(10).iterrows():
                    parts.append(f"<tr><td>{r.get('intervention_type','')}</td><td>{r.get('status','')}</td>"
                                 f"<td>{r.get('frequency','')}</td><td>{r.get('start_date','')}</td></tr>")
                parts.append("</table>")
            else:
                parts.append("<p>No interventions.</p>")
            parts.append("</body></html>")
            st.download_button('Intervention Plan (HTML)', "\n".join(parts).encode('utf-8'),
                f"{student_name.lower().replace(' ','_')}_intervention.html", 'text/html')

    # ── Action buttons ────────────────────────────────────────────────────
    st.markdown("")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("Add Assessment"):
            st.session_state['redirect_to_entry'] = True
            st.session_state['entry_student_name'] = student_name
            if not student_records.empty:
                st.session_state['entry_grade_prefill'] = student_records.iloc[-1]['grade_level']
            st.rerun()
    with a2:
        if st.button("Add Intervention"):
            st.session_state['add_intervention'] = True
            st.session_state['intervention_student_name'] = student_name
