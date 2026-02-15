"""
Teacher Dashboard Page
Daily workflow engine: action queue, tier distribution, intervention coverage,
class growth metrics, and skill-group clustering.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from core.database import (
    get_all_students, get_db_connection,
    get_all_assessments, get_all_scores, get_all_interventions,
)
from core.tier_engine import (
    assign_tiers_bulk, TIER_CORE, TIER_STRATEGIC, TIER_INTENSIVE, TIER_UNKNOWN,
    is_needs_support,
)
from core.priority_engine import compute_priority_students
from core.growth_engine import compute_period_growth, compute_cohort_growth_summary
from core.benchmarks import (
    MEASURES_BY_GRADE, MEASURE_LABELS, GRADE_ALIASES,
    get_benchmark_status, get_support_level,
)
from core.math_benchmarks import (
    MATH_MEASURES_BY_GRADE, MATH_MEASURE_LABELS, get_math_benchmark_status,
    get_math_support_level,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIER_BG = {
    'Core (Tier 1)':      ('#c3e6cb', '#155724'),
    'Strategic (Tier 2)': ('#ffeeba', '#856404'),
    'Intensive (Tier 3)': ('#f5c6cb', '#721c24'),
}

_PRIORITY_ICON = {
    'HIGH': '!!!',
    'MED': '!!',
    'LOW': '!',
}


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

def show_teacher_dashboard():
    st.title("Teacher Dashboard")

    students_df = get_all_students()
    if students_df.empty:
        st.warning("No students found.")
        return

    teachers = sorted([t for t in students_df['teacher_name'].dropna().unique() if t])
    if not teachers:
        st.warning("No teachers found in the system.")
        return

    # Filters
    f1, f2 = st.columns([2, 1])
    with f1:
        selected_teacher = st.selectbox("Select Teacher", teachers)
    with f2:
        school_years = sorted(students_df['school_year'].unique().tolist())
        selected_year = st.selectbox("School Year", school_years, index=len(school_years) - 1)

    teacher_students = students_df[
        (students_df['teacher_name'] == selected_teacher) &
        (students_df['school_year'] == selected_year)
    ]

    if teacher_students.empty:
        st.warning(f"No students found for {selected_teacher} in {selected_year}.")
        return

    st.markdown(f"### Today's Dashboard for {selected_teacher}")
    st.caption(f"{len(teacher_students)} students | {selected_year}")

    # ── Load data for engines ─────────────────────────────────────────────
    reading_assessments = get_all_assessments(subject='Reading', school_year=selected_year)
    math_assessments = get_all_assessments(subject='Math', school_year=selected_year)
    reading_scores = get_all_scores(subject='Reading', school_year=selected_year)
    math_scores = get_all_scores(subject='Math', school_year=selected_year)
    all_interventions = get_all_interventions(school_year=selected_year)

    # Filter to this teacher's students
    t_ids = set(teacher_students['student_id'].unique())
    t_reading_scores = reading_scores[reading_scores['student_id'].isin(t_ids)] if not reading_scores.empty else pd.DataFrame()
    t_math_scores = math_scores[math_scores['student_id'].isin(t_ids)] if not math_scores.empty else pd.DataFrame()
    t_reading_assess = reading_assessments[reading_assessments['student_id'].isin(t_ids)] if not reading_assessments.empty else pd.DataFrame()
    t_math_assess = math_assessments[math_assessments['student_id'].isin(t_ids)] if not math_assessments.empty else pd.DataFrame()
    t_interventions = all_interventions[all_interventions['student_id'].isin(t_ids)] if not all_interventions.empty else pd.DataFrame()

    # ── Teacher Action Queue ──────────────────────────────────────────────
    st.markdown("")
    st.subheader("Action Queue")
    st.caption("Students needing your attention today, ranked by urgency.")

    # Compute priority for both subjects
    reading_priority = compute_priority_students(
        teacher_students, t_reading_scores, t_interventions, t_reading_assess,
        subject='Reading', school_year=selected_year,
    )
    math_priority = compute_priority_students(
        teacher_students, t_math_scores, t_interventions, t_math_assess,
        subject='Math', school_year=selected_year,
    )

    # Combine with subject label
    if not reading_priority.empty:
        reading_priority = reading_priority[reading_priority['priority_score'] > 0].copy()
        reading_priority['subject'] = 'Reading'
    if not math_priority.empty:
        math_priority = math_priority[math_priority['priority_score'] > 0].copy()
        math_priority['subject'] = 'Math'

    combined_priority = pd.concat([reading_priority, math_priority], ignore_index=True)
    if not combined_priority.empty:
        combined_priority = combined_priority.sort_values('priority_score', ascending=False).reset_index(drop=True)

        def _priority_label(score):
            if score >= 6:
                return 'HIGH'
            elif score >= 3:
                return 'MED'
            return 'LOW'

        disp = combined_priority.head(20).copy()
        disp['Priority'] = disp['priority_score'].apply(_priority_label)
        disp['Action Needed'] = disp['priority_reasons'].apply(
            lambda r: '; '.join(r) if isinstance(r, list) else str(r))
        disp['Has Intervention'] = disp['has_active_intervention'].map({True: 'Yes', False: 'No'})

        action_tbl = disp[['Priority', 'student_name', 'subject', 'support_tier',
                           'Action Needed', 'days_since_last_assessment']].copy()
        action_tbl.columns = ['Priority', 'Student', 'Subject', 'Tier', 'Action Needed', 'Days Since Assess.']
        action_tbl['Days Since Assess.'] = action_tbl['Days Since Assess.'].apply(
            lambda x: f"{x:.0f}" if pd.notna(x) else '--')

        st.markdown(_render_colored_table(action_tbl, {'Tier': _TIER_BG}, max_height=450),
                    unsafe_allow_html=True)
    else:
        st.success("No urgent actions at this time. All students appear stable.")

    # ── Tier Distribution ─────────────────────────────────────────────────
    st.markdown("")
    st.subheader("Tier Distribution")

    td1, td2 = st.columns(2)

    # Reading tiers
    with td1:
        st.markdown("**Reading**")
        r_tiered = assign_tiers_bulk(teacher_students, t_reading_scores, t_reading_assess,
                                      subject='Reading', school_year=selected_year)
        if not r_tiered.empty:
            tier_counts = r_tiered['support_tier'].value_counts()
            core_n = tier_counts.get(TIER_CORE, 0)
            strat_n = tier_counts.get(TIER_STRATEGIC, 0)
            int_n = tier_counts.get(TIER_INTENSIVE, 0)
            unk_n = tier_counts.get(TIER_UNKNOWN, 0)

            fig = go.Figure(data=[go.Pie(
                labels=['Core', 'Strategic', 'Intensive', 'Unknown'],
                values=[core_n, strat_n, int_n, unk_n],
                marker_colors=['#28a745', '#ffc107', '#dc3545', '#6c757d'],
                hole=0.4,
                textinfo='value+percent',
            )])
            fig.update_layout(height=280, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

            # Tier-split intervention coverage
            active_ids = set(t_interventions[t_interventions['status'] == 'Active']['student_id'].unique()) if not t_interventions.empty else set()
            strat_ids = set(r_tiered[r_tiered['support_tier'] == TIER_STRATEGIC]['student_id'])
            int_ids = set(r_tiered[r_tiered['support_tier'] == TIER_INTENSIVE]['student_id'])
            st.caption(f"Intervention coverage: Strategic {len(strat_ids & active_ids)}/{strat_n} | "
                       f"Intensive {len(int_ids & active_ids)}/{int_n}")
        else:
            st.info("No reading scores.")

    # Math tiers
    with td2:
        st.markdown("**Math**")
        m_tiered = assign_tiers_bulk(teacher_students, t_math_scores, None,
                                      subject='Math', school_year=selected_year)
        if not m_tiered.empty:
            tier_counts = m_tiered['support_tier'].value_counts()
            core_n = tier_counts.get(TIER_CORE, 0)
            strat_n = tier_counts.get(TIER_STRATEGIC, 0)
            int_n = tier_counts.get(TIER_INTENSIVE, 0)
            unk_n = tier_counts.get(TIER_UNKNOWN, 0)

            fig = go.Figure(data=[go.Pie(
                labels=['Core', 'Strategic', 'Intensive', 'Unknown'],
                values=[core_n, strat_n, int_n, unk_n],
                marker_colors=['#28a745', '#ffc107', '#dc3545', '#6c757d'],
                hole=0.4,
                textinfo='value+percent',
            )])
            fig.update_layout(height=280, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

            active_ids = set(t_interventions[t_interventions['status'] == 'Active']['student_id'].unique()) if not t_interventions.empty else set()
            strat_ids = set(m_tiered[m_tiered['support_tier'] == TIER_STRATEGIC]['student_id'])
            int_ids = set(m_tiered[m_tiered['support_tier'] == TIER_INTENSIVE]['student_id'])
            st.caption(f"Intervention coverage: Strategic {len(strat_ids & active_ids)}/{strat_n} | "
                       f"Intensive {len(int_ids & active_ids)}/{int_n}")
        else:
            st.info("No math scores.")

    # ── Median Class Growth ───────────────────────────────────────────────
    st.markdown("")
    st.subheader("Class Growth")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Reading Growth**")
        r_growth = compute_period_growth(t_reading_scores, subject='Reading',
                                          from_period='Fall', to_period='Winter',
                                          school_year=selected_year)
        r_summary = compute_cohort_growth_summary(r_growth)
        gm1, gm2, gm3 = st.columns(3)
        with gm1:
            st.metric("Median Growth", f"{r_summary['median_growth']:+.1f}" if r_summary['median_growth'] is not None else "N/A")
        with gm2:
            st.metric("% Improving", f"{r_summary['pct_improving']:.0f}%")
        with gm3:
            st.metric("% Declining", f"{r_summary['pct_declining']:.0f}%")

    with g2:
        st.markdown("**Math Growth**")
        m_growth = compute_period_growth(t_math_scores, subject='Math',
                                          from_period='Fall', to_period='Winter',
                                          school_year=selected_year)
        m_summary = compute_cohort_growth_summary(m_growth)
        gm1, gm2, gm3 = st.columns(3)
        with gm1:
            st.metric("Median Growth", f"{m_summary['median_growth']:+.1f}" if m_summary['median_growth'] is not None else "N/A")
        with gm2:
            st.metric("% Improving", f"{m_summary['pct_improving']:.0f}%")
        with gm3:
            st.metric("% Declining", f"{m_summary['pct_declining']:.0f}%")

    # ── Skill-Group Clustering ────────────────────────────────────────────
    st.markdown("")
    st.subheader("Skill Groups")
    st.caption("Students grouped by shared deficit areas for small-group instruction.")

    sg1, sg2 = st.columns(2)

    with sg1:
        st.markdown("**Reading Skill Groups**")
        reading_groups = _compute_skill_groups(teacher_students, t_reading_assess, subject='Reading')
        if reading_groups:
            for skill, names in reading_groups.items():
                st.markdown(f"**{skill}** ({len(names)} students)")
                st.caption(", ".join(names))
        else:
            st.info("No below-benchmark reading measures to cluster.")

    with sg2:
        st.markdown("**Math Skill Groups**")
        math_groups = _compute_skill_groups(teacher_students, t_math_assess, subject='Math')
        if math_groups:
            for skill, names in math_groups.items():
                st.markdown(f"**{skill}** ({len(names)} students)")
                st.caption(", ".join(names))
        else:
            st.info("No below-benchmark math measures to cluster.")

    # ── Student Roster ────────────────────────────────────────────────────
    st.markdown("")
    with st.expander("Full Student Roster", expanded=False):
        combined_df = teacher_students[['student_id', 'student_name', 'grade_level', 'class_name']].copy()

        if not r_tiered.empty:
            r_merge = r_tiered[['student_id', 'overall_score', 'support_tier']].copy()
            r_merge.columns = ['student_id', 'reading_score', 'reading_tier']
            combined_df = combined_df.merge(r_merge, on='student_id', how='left')

        if not m_tiered.empty:
            m_merge = m_tiered[['student_id', 'overall_score', 'support_tier']].copy()
            m_merge.columns = ['student_id', 'math_score', 'math_tier']
            combined_df = combined_df.merge(m_merge, on='student_id', how='left')

        disp_cols = ['student_name', 'grade_level']
        disp_names = ['Student', 'Grade']
        if 'reading_score' in combined_df.columns:
            disp_cols += ['reading_score', 'reading_tier']
            disp_names += ['Reading Score', 'Reading Tier']
        if 'math_score' in combined_df.columns:
            disp_cols += ['math_score', 'math_tier']
            disp_names += ['Math Score', 'Math Tier']

        roster = combined_df[disp_cols].copy()
        roster.columns = disp_names
        for col in ['Reading Score', 'Math Score']:
            if col in roster.columns:
                roster[col] = roster[col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "--")

        tier_color_cols = {}
        for col in ['Reading Tier', 'Math Tier']:
            if col in roster.columns:
                tier_color_cols[col] = _TIER_BG

        st.markdown(_render_colored_table(roster, tier_color_cols, max_height=500),
                    unsafe_allow_html=True)

        st.download_button("Download Roster (CSV)", roster.to_csv(index=False),
                           f"teacher_roster_{selected_teacher.replace(' ', '_')}.csv", "text/csv")


# ---------------------------------------------------------------------------
# Skill-group clustering helper
# ---------------------------------------------------------------------------

def _compute_skill_groups(students_df, assessments_df, subject='Reading'):
    """Group students by shared below-benchmark measures."""
    if assessments_df is None or assessments_df.empty:
        return {}

    grade_alias_fn = GRADE_ALIASES.get
    measures_by_grade = MEASURES_BY_GRADE if subject == 'Reading' else MATH_MEASURES_BY_GRADE
    bm_fn = get_benchmark_status if subject == 'Reading' else get_math_benchmark_status
    label_map = MEASURE_LABELS if subject == 'Reading' else MATH_MEASURE_LABELS

    # For each student, find which measures are below benchmark
    skill_map = {}  # measure_label -> [student_names]

    for _, stu in students_df.iterrows():
        sid = stu['student_id']
        name = stu['student_name']
        grade = stu['grade_level']
        g_alias = grade_alias_fn(str(grade))
        if not g_alias:
            continue
        grade_measures = measures_by_grade.get(g_alias, [])

        stu_assess = assessments_df[assessments_df['student_id'] == sid]
        if stu_assess.empty:
            continue

        # Get latest period
        period_order = {'Fall': 1, 'Winter': 2, 'Spring': 3, 'EOY': 4}
        if 'assessment_period' in stu_assess.columns:
            stu_assess = stu_assess.copy()
            stu_assess['_po'] = stu_assess['assessment_period'].map(period_order).fillna(0)
            latest_period_row = stu_assess.sort_values('_po', ascending=False).iloc[0]
            latest_period = latest_period_row.get('assessment_period', 'Fall')
        else:
            latest_period = 'Fall'

        for m in grade_measures:
            m_df = stu_assess[stu_assess['assessment_type'] == m]
            if m_df.empty:
                continue
            try:
                raw_float = float(m_df.iloc[-1].get('score_value', 0))
            except (ValueError, TypeError):
                raw_float = m_df.iloc[-1].get('score_normalized')
            if raw_float is None:
                continue

            bm_status = bm_fn(m, grade, latest_period, raw_float)
            if bm_status in ('Below Benchmark', 'Well Below Benchmark'):
                label = label_map.get(m, m)
                full_label = f"{label} ({bm_status})"
                if full_label not in skill_map:
                    skill_map[full_label] = []
                skill_map[full_label].append(name)

    # Sort by group size (largest first)
    return dict(sorted(skill_map.items(), key=lambda x: -len(x[1])))
