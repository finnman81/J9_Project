"""
Teacher dashboard API: data filtered by teacher and school year.
Uses v_support_status / v_priority_students when available; fallback to legacy.
"""
import logging
import pandas as pd
from fastapi import APIRouter

logger = logging.getLogger(__name__)

from core.database import (
    get_all_students,
    get_all_enrollments,
    get_all_assessments,
    get_all_scores,
    get_all_interventions,
    get_v_support_status,
    get_v_priority_students,
    get_v_growth_last_two,
)
from core.tier_engine import assign_tiers_bulk, is_needs_support
from core.priority_engine import compute_priority_students
from core.growth_engine import compute_period_growth, compute_cohort_growth_summary
from api.serializers import dataframe_to_records

router = APIRouter()


def _tier_to_long(tier: str) -> str:
    if tier == "Core":
        return "Core (Tier 1)"
    if tier == "Strategic":
        return "Strategic (Tier 2)"
    if tier == "Intensive":
        return "Intensive (Tier 3)"
    return tier or "Unknown"


@router.get("/teacher/teachers")
def list_teachers():
    try:
        df = get_all_enrollments()
    except Exception as e:
        logger.debug("list_teachers: get_all_enrollments failed: %s", e)
        df = pd.DataFrame()
    if df.empty:
        df = get_all_students()
    if df.empty:
        return {"teachers": []}
    teachers = sorted([t for t in df["teacher_name"].dropna().unique() if t])
    return {"teachers": teachers}


@router.get("/teacher/dashboard")
def teacher_dashboard(
    teacher: str,
    school_year: str,
    subject: str = "Reading",
):
    # Try view-based path first
    try:
        ss_df = get_v_support_status(
            teacher_name=teacher,
            school_year=school_year,
            subject_area=subject,
        )
        if ss_df is not None and not ss_df.empty:
            pr_df = get_v_priority_students(
                teacher_name=teacher,
                school_year=school_year,
                subject_area=subject,
            )
            gr_df = get_v_growth_last_two(
                teacher_name=teacher,
                school_year=school_year,
                subject_area=subject,
            )
            score_col = "overall_literacy_score" if subject == "Reading" else "overall_math_score"
            needs = ss_df["tier"].isin(["Intensive", "Strategic"]).sum()
            students_out = []
            for _, row in ss_df.iterrows():
                students_out.append({
                    "student_id": row.get("enrollment_id"),
                    "student_name": row.get("display_name"),
                    "display_name": row.get("display_name"),
                    "enrollment_id": row.get("enrollment_id"),
                    "grade_level": row.get("grade_level"),
                    "class_name": row.get("class_name"),
                    "teacher_name": row.get("teacher_name"),
                    "school_year": row.get("school_year"),
                    score_col: row.get("latest_score"),
                    "support_tier": _tier_to_long(row.get("tier")),
                    "risk_level": None,
                    "trend": None,
                })
            if pr_df is not None and not pr_df.empty and "trend" in pr_df.columns:
                trend_by_eid = pr_df.set_index("enrollment_id")["trend"].to_dict()
                for s in students_out:
                    s["trend"] = trend_by_eid.get(s.get("enrollment_id"), "Unknown")
            priority_records = []
            if pr_df is not None and not pr_df.empty:
                priority_records = dataframe_to_records(
                    pr_df[pr_df["priority_score"] > 0].copy()
                )
            growth_summary = {}
            if gr_df is not None and not gr_df.empty and "growth" in gr_df.columns:
                g = gr_df["growth"].dropna()
                n = len(g)
                if n:
                    growth_summary = {
                        "median_growth": round(float(g.median()), 1),
                        "pct_improving": round(100.0 * (gr_df["trend"] == "Improving").sum() / n, 1),
                        "pct_declining": round(100.0 * (gr_df["trend"] == "Declining").sum() / n, 1),
                        "n": n,
                    }
            return {
                "teacher": teacher,
                "school_year": school_year,
                "subject": subject,
                "students": students_out,
                "summary": {"total_students": len(ss_df), "needs_support": int(needs)},
                "priority_students": priority_records,
                "growth_summary": growth_summary,
            }
    except Exception as e:
        logger.debug("Teacher dashboard view path skipped: %s", e)

    # Legacy path
    students_df = get_all_students(teacher_name=teacher, school_year=school_year)
    if students_df.empty:
        return {
            "teacher": teacher,
            "school_year": school_year,
            "subject": subject,
            "students": [],
            "summary": {"total_students": 0, "needs_support": 0},
            "priority_students": [],
            "growth_summary": {},
        }

    t_ids = set(students_df["student_id"].unique())
    all_scores = get_all_scores(subject=subject, school_year=school_year)
    all_assessments = get_all_assessments(subject=subject, school_year=school_year)
    all_interventions = get_all_interventions(school_year=school_year)

    t_scores = all_scores[all_scores["student_id"].isin(t_ids)] if not all_scores.empty else pd.DataFrame()
    tiered = assign_tiers_bulk(
        students_df[["student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year"]],
        t_scores,
        all_assessments,
        subject=subject,
        school_year=school_year,
    )
    needs_support = int(tiered["support_tier"].apply(is_needs_support).sum()) if not tiered.empty else 0

    priority_df = compute_priority_students(
        students_df[["student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year"]],
        all_scores,
        all_interventions,
        all_assessments,
        subject=subject,
        school_year=school_year,
    )
    teacher_priority = priority_df[priority_df["student_id"].isin(t_ids)] if not priority_df.empty else pd.DataFrame()
    priority_records = dataframe_to_records(teacher_priority)

    growth_df = compute_period_growth(all_scores, subject=subject, from_period="Fall", to_period="Winter", school_year=school_year)
    growth_teacher = growth_df[growth_df["student_id"].isin(t_ids)] if not growth_df.empty else pd.DataFrame()
    growth_summary = compute_cohort_growth_summary(growth_teacher)

    score_col = "overall_literacy_score" if subject == "Reading" else "overall_math_score"
    merged = students_df.merge(
        tiered[["student_id", "support_tier"]],
        on="student_id",
        how="left",
    )
    if not t_scores.empty and score_col in t_scores.columns:
        latest = t_scores.sort_values("calculated_at", ascending=False).groupby("student_id", as_index=False).first()
        merged = merged.merge(
            latest[["student_id", score_col, "risk_level", "trend"]],
            on="student_id",
            how="left",
        )

    return {
        "teacher": teacher,
        "school_year": school_year,
        "subject": subject,
        "students": dataframe_to_records(merged),
        "summary": {
            "total_students": len(students_df),
            "needs_support": needs_support,
        },
        "priority_students": priority_records,
        "growth_summary": growth_summary,
    }
