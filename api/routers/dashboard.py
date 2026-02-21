"""
Dashboard API: reading and math overview data with filters, KPIs, tiers, priority, growth.
"""
import logging
import pandas as pd
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

from core.database import (
    get_all_students,
    get_all_enrollments,
    get_all_scores,
    get_all_assessments,
    get_all_interventions,
    get_v_support_status,
    get_v_priority_students,
    get_v_growth_last_two,
)
from core.tier_engine import (
    assign_tiers_bulk,
    TIER_STRATEGIC,
    TIER_INTENSIVE,
    is_needs_support,
)
from core.priority_engine import compute_priority_students, get_top_priority
from core.data_health import compute_data_health
from core.growth_engine import compute_period_growth, compute_cohort_growth_summary
from api.serializers import dataframe_to_records

router = APIRouter()

PERIOD_ORDER = {"Fall": 1, "Winter": 2, "Spring": 3, "EOY": 4}


def _empty_dashboard_response():
    return {
        "summary": {
            "total_students": 0,
            "needs_support": 0,
            "avg_score": None,
            "completion_rate": 0,
            "health": {},
            "intervention_coverage": "",
        },
        "students": [],
        "priority_students": [],
        "growth_summary": {"median_growth": None, "pct_improving": 0, "pct_declining": 0, "n": 0},
        "score_distribution": [],
        "by_grade": [],
    }


def _latest_score_per_student(scores_df: pd.DataFrame) -> pd.DataFrame:
    if scores_df is None or scores_df.empty:
        return pd.DataFrame()
    if "assessment_period" not in scores_df.columns:
        return scores_df
    scores_df = scores_df.copy()
    scores_df["_period_ord"] = scores_df["assessment_period"].map(
        lambda p: PERIOD_ORDER.get(p, 0)
    )
    latest = (
        scores_df.sort_values(["_period_ord", "calculated_at"], ascending=[False, False])
        .groupby("student_id", as_index=False)
        .first()
    )
    latest = latest.drop(columns=["_period_ord"], errors="ignore")
    return latest


def _tier_to_long(tier: str) -> str:
    """Map view tier (Core/Strategic/Intensive) to legacy display form."""
    if tier == "Core":
        return "Core (Tier 1)"
    if tier == "Strategic":
        return "Strategic (Tier 2)"
    if tier == "Intensive":
        return "Intensive (Tier 3)"
    return tier or "Unknown"


def _build_dashboard(
    subject: str,
    grade_level: str | None,
    class_name: str | None,
    teacher_name: str | None,
    school_year: str | None,
):
    # Try view-based path first (requires migration_v3 + student_enrollments)
    try:
        ss_df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if ss_df is not None and not ss_df.empty:
            pr_df = get_v_priority_students(
                teacher_name=teacher_name,
                school_year=school_year,
                subject_area=subject,
                grade_level=grade_level,
                class_name=class_name,
            )
            gr_df = get_v_growth_last_two(
                teacher_name=teacher_name,
                school_year=school_year,
                subject_area=subject,
                grade_level=grade_level,
                class_name=class_name,
            )
            total = len(ss_df)
            assessed = ss_df["latest_score"].notna().sum()
            needs = ss_df["tier"].isin(["Intensive", "Strategic"]).sum()
            overdue = (ss_df["days_since_assessment"] > 90).sum() if "days_since_assessment" in ss_df.columns else 0
            need_ss = ss_df[ss_df["tier"].isin(["Intensive", "Strategic"])]
            covered = need_ss["has_active_intervention"].eq(True).sum() if not need_ss.empty else 0
            cov_pct = f"{covered}/{needs} ({covered/needs*100:.0f}%)" if needs else "N/A"
            score_col = "overall_literacy_score" if subject == "Reading" else "overall_math_score"
            # Students list: map view columns to legacy shape
            students_out = []
            for _, row in ss_df.iterrows():
                students_out.append({
                    "enrollment_id": row.get("enrollment_id"),
                    "display_name": row.get("display_name"),
                    "grade_level": row.get("grade_level"),
                    "class_name": row.get("class_name"),
                    "teacher_name": row.get("teacher_name"),
                    "school_year": row.get("school_year"),
                    score_col: row.get("latest_score"),
                    "support_tier": _tier_to_long(row.get("tier")),
                    "assessment_period": row.get("latest_period"),
                })
            # Trend: merge from priority view (has trend)
            if pr_df is not None and not pr_df.empty and "trend" in pr_df.columns:
                trend_by_enrollment = pr_df.set_index("enrollment_id")["trend"].to_dict()
                for s in students_out:
                    eid = s.get("enrollment_id")
                    if eid in trend_by_enrollment:
                        s["trend"] = trend_by_enrollment[eid]
                    else:
                        s["trend"] = "Unknown"
            else:
                for s in students_out:
                    s["trend"] = "Unknown"
            priority_records = []
            if pr_df is not None and not pr_df.empty:
                top = pr_df[pr_df["priority_score"] > 0].head(50)
                for _, row in top.iterrows():
                    priority_records.append({
                        "enrollment_id": row.get("enrollment_id"),
                        "student_name": row.get("display_name"),
                        "display_name": row.get("display_name"),
                        "grade_level": row.get("grade_level"),
                        "teacher_name": row.get("teacher_name"),
                        "support_tier": _tier_to_long(row.get("tier")),
                        "has_active_intervention": row.get("has_active_intervention"),
                        "days_since_last_assessment": row.get("days_since_assessment"),
                        "growth_trend": row.get("trend"),
                        "priority_score": row.get("priority_score"),
                        "priority_reasons": row.get("reasons"),
                    })
            growth_summary = {"median_growth": None, "pct_improving": 0, "pct_declining": 0, "n": 0}
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
            scores = ss_df["latest_score"].dropna()
            score_distribution = scores.tolist() if len(scores) else []
            by_grade = []
            if "grade_level" in ss_df.columns and "latest_score" in ss_df.columns:
                grade_avg = ss_df.groupby("grade_level")["latest_score"].mean().reset_index()
                grade_avg.columns = ["grade_level", "average_score"]
                by_grade = dataframe_to_records(grade_avg)
            return {
                "summary": {
                    "total_students": int(total),
                    "needs_support": int(needs),
                    "avg_score": float(scores.mean()) if len(scores) else None,
                    "completion_rate": round(100.0 * assessed / total, 1) if total else 0,
                    "health": {},
                    "intervention_coverage": cov_pct,
                },
                "students": students_out,
                "priority_students": priority_records,
                "growth_summary": growth_summary,
                "score_distribution": score_distribution,
                "by_grade": by_grade,
            }
    except Exception as e:
        logger.debug("View-based dashboard path skipped: %s", e)

    # Prefer enrollments (students_core + student_enrollments); fallback to legacy students table
    enrollments_df = pd.DataFrame()
    try:
        enrollments_df = get_all_enrollments(
            grade_level=grade_level,
            class_name=class_name,
            teacher_name=teacher_name,
            school_year=school_year,
        )
    except Exception as e:
        logger.debug("get_all_enrollments failed, using legacy path: %s", e)

    if enrollments_df.empty:
        students_df = get_all_students(
            grade_level=grade_level,
            class_name=class_name,
            teacher_name=teacher_name,
            school_year=school_year,
        )
        if students_df.empty:
            return _empty_dashboard_response()
        # Legacy path: add synthetic enrollment_id so frontend can still link
        students_df["enrollment_id"] = students_df["student_id"].astype(str)
        students_df["display_name"] = students_df["student_name"]
        students_df["legacy_student_id"] = students_df["student_id"]
        students_df_for_merge = students_df.copy()
    else:
        # Enrollment path: build a frame that has student_id for score/tier merge (legacy_student_id)
        students_df_for_merge = enrollments_df.copy()
        students_df_for_merge["student_id"] = students_df_for_merge["legacy_student_id"]
        students_df_for_merge["student_name"] = students_df_for_merge["display_name"]
        # Keep enrollment_id, display_name for API output
        if "legacy_student_id" not in students_df_for_merge.columns:
            students_df_for_merge["legacy_student_id"] = None

    students_df = students_df_for_merge
    if students_df.empty:
        return _empty_dashboard_response()

    yr = school_year
    all_scores = get_all_scores(subject=subject, school_year=yr)
    all_assessments = get_all_assessments(subject=subject, school_year=yr)
    all_interventions = get_all_interventions(school_year=yr)

    latest_scores = _latest_score_per_student(all_scores)
    score_col = "overall_literacy_score" if subject == "Reading" else "overall_math_score"
    if latest_scores.empty:
        merged = students_df.copy()
        merged["overall_literacy_score"] = None
        merged["overall_math_score"] = None
        merged["risk_level"] = None
        merged["trend"] = None
        merged["assessment_period"] = None
    else:
        cols = ["student_id", score_col, "risk_level", "trend", "assessment_period"]
        cols = [c for c in cols if c in latest_scores.columns]
        merged = students_df.merge(
            latest_scores[["student_id"] + [c for c in cols if c != "student_id"]],
            on="student_id",
            how="left",
        )

    tier_input = merged[["student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year"]].drop_duplicates()
    tiered = assign_tiers_bulk(
        tier_input,
        all_scores,
        all_assessments,
        subject=subject,
        school_year=yr,
    )
    if not tiered.empty and "support_tier" in tiered.columns:
        merged = merged.drop(columns=["support_tier"], errors="ignore")
        merged = merged.merge(
            tiered[["student_id", "support_tier"]],
            on="student_id",
            how="left",
        )
    else:
        merged["support_tier"] = None

    total_students = merged["student_id"].nunique()
    needs_support = int(tiered["support_tier"].apply(is_needs_support).sum()) if not tiered.empty else 0
    avg_score = merged[score_col].mean() if score_col in merged.columns else None
    students_with_scores = merged[score_col].notna().sum()
    completion_rate = (students_with_scores / total_students * 100) if total_students else 0

    active_int = all_interventions[all_interventions["status"] == "Active"] if not all_interventions.empty else pd.DataFrame()
    active_int_ids = set(active_int["student_id"].unique()) if not active_int.empty else set()
    strategic_ids = set(tiered[tiered["support_tier"] == TIER_STRATEGIC]["student_id"]) if not tiered.empty else set()
    intensive_ids = set(tiered[tiered["support_tier"] == TIER_INTENSIVE]["student_id"]) if not tiered.empty else set()
    total_need = len(strategic_ids) + len(intensive_ids)
    total_covered = len(strategic_ids & active_int_ids) + len(intensive_ids & active_int_ids)
    cov_pct = f"{total_covered}/{total_need} ({total_covered/total_need*100:.0f}%)" if total_need else "N/A"

    health = compute_data_health(
        merged[["student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year"]].drop_duplicates(),
        all_assessments,
        all_scores,
        subject=subject,
        school_year=yr,
    )
    health_serializable = {k: (v if not (hasattr(v, "isoformat")) else v.isoformat()) for k, v in health.items()}

    priority_df = compute_priority_students(
        merged[["student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year"]].drop_duplicates(),
        all_scores,
        all_interventions,
        all_assessments,
        subject=subject,
        school_year=yr,
    )
    top_priority = get_top_priority(priority_df, n=50)
    priority_records = dataframe_to_records(top_priority) if not top_priority.empty else []

    growth_df = compute_period_growth(all_scores, subject=subject, from_period="Fall", to_period="Winter", school_year=yr)
    growth_summary = compute_cohort_growth_summary(growth_df)
    growth_serializable = {
        "median_growth": growth_summary.get("median_growth"),
        "pct_improving": growth_summary.get("pct_improving", 0),
        "pct_declining": growth_summary.get("pct_declining", 0),
        "n": growth_summary.get("n", 0),
    }

    score_distribution = []
    if score_col in merged.columns:
        scores = merged[score_col].dropna()
        if not scores.empty:
            score_distribution = scores.tolist()

    by_grade = []
    if score_col in merged.columns and not merged.empty:
        grade_avg = merged.groupby("grade_level")[score_col].mean().reset_index()
        grade_avg.columns = ["grade_level", "average_score"]
        by_grade = dataframe_to_records(grade_avg)

    # Prefer enrollment_id + display_name for frontend; keep student_id for backward compat
    out_cols = [c for c in merged.columns if c in ("enrollment_id", "display_name", "student_id", "student_name", "grade_level", "class_name", "teacher_name", "school_year", score_col, "risk_level", "trend", "support_tier", "assessment_period")]
    out_cols = list(dict.fromkeys(out_cols))
    students_out = dataframe_to_records(merged[out_cols] if out_cols else merged)

    return {
        "summary": {
            "total_students": int(total_students),
            "needs_support": needs_support,
            "avg_score": float(avg_score) if avg_score is not None and not (isinstance(avg_score, float) and pd.isna(avg_score)) else None,
            "completion_rate": round(completion_rate, 1),
            "health": health_serializable,
            "intervention_coverage": cov_pct,
        },
        "students": students_out,
        "priority_students": priority_records,
        "growth_summary": growth_serializable,
        "score_distribution": score_distribution,
        "by_grade": by_grade,
    }


@router.get("/dashboard/reading")
def dashboard_reading(
    grade_level: str | None = None,
    class_name: str | None = None,
    teacher_name: str | None = None,
    school_year: str | None = None,
):
    try:
        return _build_dashboard("Reading", grade_level, class_name, teacher_name, school_year)
    except Exception:
        logger.exception("dashboard_reading failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard/math")
def dashboard_math(
    grade_level: str | None = None,
    class_name: str | None = None,
    teacher_name: str | None = None,
    school_year: str | None = None,
):
    try:
        return _build_dashboard("Math", grade_level, class_name, teacher_name, school_year)
    except Exception:
        logger.exception("dashboard_math failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard/filters")
def dashboard_filters():
    """Return distinct grade_level, class_name, teacher_name, school_year for filter dropdowns."""
    try:
        df = get_all_enrollments()
    except Exception as e:
        logger.debug("dashboard_filters: get_all_enrollments failed, using legacy: %s", e)
        df = pd.DataFrame()
    if df.empty:
        df = get_all_students()
    if df.empty:
        return {"grade_levels": [], "classes": [], "teachers": [], "school_years": []}
    grades = sorted(df["grade_level"].dropna().unique().tolist())
    classes = ["All"] + sorted([c for c in df["class_name"].dropna().unique() if c])
    teachers = ["All"] + sorted([t for t in df["teacher_name"].dropna().unique() if t])
    years = ["All"] + sorted(df["school_year"].unique().tolist())
    return {
        "grade_levels": grades,
        "classes": classes,
        "teachers": teachers,
        "school_years": years,
    }
