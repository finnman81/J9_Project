"""
Metrics API: teacher KPIs, priority students, growth, distribution.
Uses SQL views v_support_status, v_priority_students, v_growth_last_two.
"""
import logging
import time
import pandas as pd
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

from core.database import (
    get_v_support_status,
    get_v_priority_students,
    get_v_growth_last_two,
    get_benchmark_thresholds,
    get_db_connection,
)
from core.erb_scoring import ERB_SUBTESTS, ERB_SUBTEST_LABELS, parse_erb_score_value, get_erb_independent_norm
from api.serializers import dataframe_to_records

router = APIRouter()

# Grade order for charts and filters: Kindergarten → Eighth (school flow 5, 6, 7, 8)
GRADE_ORDER = ["Kindergarten", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]


def _dedupe_support_by_student(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse multiple enrollments per student_uuid down to the most recent row.

    Uses school_year (when present) to pick the latest enrollment for each student.
    """
    if df is None or df.empty or "student_uuid" not in df.columns:
        return df
    df = df.copy()
    if "school_year" in df.columns:
        df["_year_sort"] = df["school_year"].astype(str)
        df = df.sort_values(["student_uuid", "_year_sort"], ascending=[True, False])
    else:
        df = df.sort_values(["student_uuid"])
    df = df.drop_duplicates(subset=["student_uuid"], keep="first")
    return df.drop(columns=["_year_sort"], errors="ignore")


def _dedupe_priority_by_student(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse multiple enrollments per student for priority table to one row per student."""
    if df is None or df.empty:
        return df
    # Attach student_uuid via student_enrollments if not present
    if "student_uuid" not in df.columns:
        conn = get_db_connection()
        try:
            map_df = pd.read_sql_query(
                "SELECT enrollment_id, student_uuid FROM public.student_enrollments",
                conn,
            )
        except Exception:
            conn.close()
            return df
        conn.close()
        df = df.merge(map_df, on="enrollment_id", how="left")
    if "student_uuid" not in df.columns:
        return df
    df = df.copy()
    # Prefer higher priority_score, then more days_since_assessment
    df["_prio_sort"] = df.get("priority_score", 0)
    df["_days_sort"] = df.get("days_since_assessment", 0)
    df = df.sort_values(
        ["student_uuid", "_prio_sort", "_days_sort"],
        ascending=[True, False, False],
    )
    df = df.drop_duplicates(subset=["student_uuid"], keep="first")
    return df.drop(columns=["_prio_sort", "_days_sort"], errors="ignore")


def _kpis_from_support_status(
    df: pd.DataFrame,
    current_period: str | None = None,
    current_school_year: str | None = None,
):
    """Compute KPI strip from v_support_status rows. Optional current_period/current_school_year for 'assessed this window'."""
    empty = {
        "total_students": 0,
        "assessed_students": 0,
        "assessed_pct": 0.0,
        "monitor_count": 0,
        "monitor_pct": 0.0,
        "needs_support_count": 0,
        "needs_support_pct": 0.0,
        "support_gap_count": 0,
        "support_gap_pct": 0.0,
        "overdue_count": 0,
        "overdue_pct": 0.0,
        "median_days_since_assessment": None,
        "intervention_coverage_count": 0,
        "intervention_coverage_pct": 0.0,
        "assessed_this_window_count": 0,
        "assessed_this_window_pct": 0.0,
        "tier_moved_up_count": 0,
        "tier_moved_down_count": 0,
    }
    if df is None or df.empty:
        return empty
    # Deduplicate to one row per student (latest enrollment per student_uuid)
    df = _dedupe_support_by_student(df)
    total = len(df)
    assessed = df["latest_score"].notna().sum()
    # Support status: On Track / Monitor / Needs Support (tier: Core / Strategic / Intensive)
    support_status = df.get("support_status")
    monitor = (support_status == "Monitor").sum() if support_status is not None else 0
    needs = df["tier"].isin(["Intensive", "Strategic"]).sum() if "tier" in df.columns else 0
    # Support gap = Needs Support with no active intervention
    need_df = df[df["tier"].isin(["Intensive", "Strategic"])]
    support_gap = (need_df["has_active_intervention"].eq(False).sum() if "has_active_intervention" in need_df.columns else 0) if not need_df.empty else 0
    covered = need_df["has_active_intervention"].eq(True).sum() if not need_df.empty else 0
    overdue = (df["days_since_assessment"] > 90).sum() if "days_since_assessment" in df.columns else 0
    days = df["days_since_assessment"].dropna() if "days_since_assessment" in df.columns else pd.Series(dtype=float)
    days = days[days >= 0]
    try:
        median_days = round(float(days.median()), 1) if len(days) > 0 and pd.notna(days.median()) else None
    except (ValueError, TypeError):
        median_days = None

    # Assessed this window: latest_period + school_year match
    assessed_window = 0
    period_col = df.get("latest_period")
    year_col = df.get("school_year")
    if period_col is not None and year_col is not None and current_period and current_school_year:
        in_window = (
            (period_col.astype(str).str.strip().str.lower() == current_period.strip().lower())
            & (year_col.astype(str) == current_school_year)
        )
        assessed_window = int(in_window.sum())
    assessed_window_pct = round(100.0 * assessed_window / total, 1) if total else 0.0

    return {
        "total_students": int(total),
        "assessed_students": int(assessed),
        "assessed_pct": round(100.0 * assessed / total, 1) if total else 0.0,
        "monitor_count": int(monitor),
        "monitor_pct": round(100.0 * monitor / total, 1) if total else 0.0,
        "needs_support_count": int(needs),
        "needs_support_pct": round(100.0 * needs / total, 1) if total else 0.0,
        "support_gap_count": int(support_gap),
        "support_gap_pct": round(100.0 * support_gap / total, 1) if total else 0.0,
        "overdue_count": int(overdue),
        "overdue_pct": round(100.0 * overdue / total, 1) if total else 0.0,
        "median_days_since_assessment": median_days,
        "intervention_coverage_count": int(covered),
        "intervention_coverage_pct": round(100.0 * covered / needs, 1) if needs else 0.0,
        "assessed_this_window_count": int(assessed_window),
        "assessed_this_window_pct": assessed_window_pct,
        "tier_moved_up_count": 0,
        "tier_moved_down_count": 0,
    }


@router.get("/metrics/teacher-kpis")
def get_teacher_kpis(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
    current_period: str | None = None,
    current_school_year: str | None = None,
):
    """Return KPI strip. Use current_period + current_school_year for '%% assessed this window' (e.g. Fall, 2024-25)."""
    t0 = time.perf_counter()
    try:
        df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None or df.empty:
            # Return empty KPIs instead of error - frontend handles empty state
            logger.info("metrics/teacher-kpis %.3fs", time.perf_counter() - t0)
            return _kpis_from_support_status(
                pd.DataFrame(),
                current_period=current_period or None,
                current_school_year=current_school_year or school_year,
            )
        out = _kpis_from_support_status(
            df,
            current_period=current_period or None,
            current_school_year=current_school_year or school_year,
        )
        logger.info("metrics/teacher-kpis %.3fs", time.perf_counter() - t0)
        return out
    except Exception as e:
        logger.exception("get_teacher_kpis failed")
        raise HTTPException(status_code=500, detail="Internal server error")


def _reasons_to_chips(reasons: str | None) -> list[str]:
    """Split reasons string into chips: Overdue, Declining, No intervention, Below benchmark."""
    if not reasons or not str(reasons).strip():
        return []
    chips = []
    s = str(reasons).lower()
    if "overdue" in s:
        chips.append("Overdue")
    if "declining" in s:
        chips.append("Declining")
    if "no active intervention" in s or "no intervention" in s:
        chips.append("No intervention")
    if "intensive tier" in s or "strategic tier" in s or "below benchmark" in s:
        chips.append("Below benchmark")
    return chips if chips else [r.strip() for r in reasons.split("|") if r.strip()][:4]


@router.get("/metrics/priority-students")
def get_priority_students(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return priority students: support_status, reason_chips, default sort (support gap > declining > overdue > lowest score)."""
    t0 = time.perf_counter()
    try:
        df = get_v_priority_students(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None:
            df = pd.DataFrame()
        df = _dedupe_priority_by_student(df)
        if df is None or df.empty:
            logger.info("metrics/priority-students %.3fs", time.perf_counter() - t0)
            return {
                "rows": [],
                "flagged_intensive": 0,
                "flagged_strategic": 0,
                "total_flagged": 0,
            }
        # Default sort: Needs Support + no intervention > Declining > Overdue > lowest score
        df = df.copy()
        support_gap = (
            df["tier"].isin(["Intensive", "Strategic"]) & (df["has_active_intervention"].eq(False))
        )
        declining = (df.get("trend") == "Declining") if "trend" in df.columns else pd.Series(False, index=df.index)
        overdue = (df["days_since_assessment"] > 90) if "days_since_assessment" in df.columns else pd.Series(False, index=df.index)
        df["_sort1"] = (~support_gap).astype(int)
        df["_sort2"] = (~declining).astype(int)
        df["_sort3"] = (~overdue).astype(int)
        df["_sort4"] = df["latest_score"].fillna(999)
        df = df.sort_values(by=["_sort1", "_sort2", "_sort3", "_sort4"], ascending=[True, True, True, True])
        df = df.drop(columns=["_sort1", "_sort2", "_sort3", "_sort4"], errors="ignore")

        flagged = df[df["priority_score"] > 0] if "priority_score" in df.columns else df
        intensive = (flagged["tier"] == "Intensive").sum() if not flagged.empty else 0
        strategic = (flagged["tier"] == "Strategic").sum() if not flagged.empty else 0
        rows_raw = dataframe_to_records(df)
        rows = []
        for r in rows_raw:
            reasons_str = r.get("reasons")
            chips = _reasons_to_chips(reasons_str)
            rows.append({**r, "reason_chips": chips})
        logger.info("metrics/priority-students %.3fs", time.perf_counter() - t0)
        return {
            "rows": rows,
            "flagged_intensive": int(intensive),
            "flagged_strategic": int(strategic),
            "total_flagged": len(flagged),
        }
    except Exception as e:
        logger.exception("get_priority_students failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics/growth")
def get_growth_metrics(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return growth KPIs from last-two view.

    Includes median/average growth, % Improving/Declining/Stable, and best/worst changes.
    """
    t0 = time.perf_counter()
    try:
        df = get_v_growth_last_two(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None or df.empty or "growth" not in df.columns:
            logger.info("metrics/growth %.3fs", time.perf_counter() - t0)
            return {
                "median_growth": None,
                "avg_growth": None,
                "pct_improving": 0.0,
                "pct_declining": 0.0,
                "pct_stable": 0.0,
                "students_with_growth_data": 0,
                "max_growth": None,
                "min_growth": None,
            }
        growth = df["growth"].dropna()
        n = len(growth)
        if n == 0:
            logger.info("metrics/growth %.3fs", time.perf_counter() - t0)
            return {
                "median_growth": None,
                "avg_growth": None,
                "pct_improving": 0.0,
                "pct_declining": 0.0,
                "pct_stable": 0.0,
                "students_with_growth_data": 0,
                "max_growth": None,
                "min_growth": None,
            }
        trend = df["trend"] if "trend" in df.columns else pd.Series(dtype=object)
        improving = (trend == "Improving").sum()
        declining = (trend == "Declining").sum()
        stable = (trend == "Stable").sum()
        median_growth = round(float(growth.median()), 1)
        avg_growth = round(float(growth.mean()), 1)
        max_growth = round(float(growth.max()), 1)
        min_growth = round(float(growth.min()), 1)
        logger.info("metrics/growth %.3fs", time.perf_counter() - t0)
        return {
            "median_growth": median_growth,
            "avg_growth": avg_growth,
            "pct_improving": round(100.0 * improving / n, 1),
            "pct_declining": round(100.0 * declining / n, 1),
            "pct_stable": round(100.0 * stable / n, 1),
            "students_with_growth_data": n,
            "max_growth": max_growth,
            "min_growth": min_growth,
        }
    except Exception:
        logger.exception("get_growth_metrics failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics/distribution")
def get_distribution(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """Return histogram bins, benchmark/support thresholds, and avg by grade."""
    t0 = time.perf_counter()
    try:
        df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        # Deduplicate to one row per student for distribution / avg-by-grade
        df = _dedupe_support_by_student(df)
        scores = df["latest_score"].dropna() if df is not None and not df.empty else pd.Series(dtype=float)
        bins = []
        total_scores = len(scores)
        if total_scores > 0:
            for low in range(0, 100, 10):
                high = low + 10
                count = ((scores >= low) & (scores < high)).sum()
                pct = round(100.0 * count / total_scores, 1)
                bins.append({"bin_min": low, "bin_max": high, "count": int(count), "pct": pct})
            count_100 = (scores >= 100).sum()
            if count_100 > 0:
                pct_100 = round(100.0 * count_100 / total_scores, 1)
                bins.append({"bin_min": 100, "bin_max": 110, "count": int(count_100), "pct": pct_100})
        avg_by_grade = []
        if df is not None and not df.empty and "grade_level" in df.columns:
            needs = df["tier"].isin(["Intensive", "Strategic"]) if "tier" in df.columns else pd.Series(False, index=df.index)
            df_grp = df.assign(_needs=needs)
            grp = df_grp.groupby("grade_level").agg(
                average_score=("latest_score", "mean"),
                total=("latest_score", "count"),
                needs_count=("_needs", "sum"),
            ).reset_index()
            grp["pct_needs_support"] = (100.0 * grp["needs_count"] / grp["total"].replace(0, 1)).round(1)
            grp["average_score"] = grp["average_score"].round(1)
            grp = grp.drop(columns=["total", "needs_count"], errors="ignore")
            order = {g: i for i, g in enumerate(GRADE_ORDER)}
            grp["_order"] = grp["grade_level"].map(lambda x: order.get(x, 99))
            grp = grp.sort_values("_order").drop(columns=["_order"], errors="ignore")
            avg_by_grade = dataframe_to_records(grp)
        thresholds_df = get_benchmark_thresholds(
            subject_area=subject,
            school_year=school_year,
        )
        support_threshold = None
        benchmark_threshold = None
        if thresholds_df is not None and not thresholds_df.empty:
            support_threshold = round(float(thresholds_df["support_threshold"].median()), 1) if "support_threshold" in thresholds_df.columns else None
            benchmark_threshold = round(float(thresholds_df["benchmark_threshold"].median()), 1) if "benchmark_threshold" in thresholds_df.columns else None
        logger.info("metrics/distribution %.3fs", time.perf_counter() - t0)
        return {
            "bins": bins,
            "avg_by_grade": avg_by_grade,
            "support_threshold": support_threshold,
            "benchmark_threshold": benchmark_threshold,
        }
    except Exception:
        logger.exception("get_distribution failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics/support-trend")
def get_support_trend(
    teacher_name: str | None = None,
    school_year: str | None = None,
    subject: str | None = None,
    grade_level: str | None = None,
    class_name: str | None = None,
):
    """
    Multi-year support need trend: % of students in Intensive/Strategic tier by school_year.

    Used by Analytics page's "Support need trends by year" chart.
    """
    try:
        df = get_v_support_status(
            teacher_name=teacher_name,
            school_year=school_year,
            subject_area=subject,
            grade_level=grade_level,
            class_name=class_name,
        )
        if df is None or df.empty or "school_year" not in df.columns:
            return {"rows": []}
        needs = df["tier"].isin(["Intensive", "Strategic"]) if "tier" in df.columns else pd.Series(False, index=df.index)
        df_grp = df.assign(_needs=needs)
        grp = df_grp.groupby("school_year").agg(
            total=("latest_score", "count"),
            needs_count=("_needs", "sum"),
        ).reset_index()
        grp["pct_needs_support"] = (100.0 * grp["needs_count"] / grp["total"].replace(0, 1)).round(1)
        grp = grp.sort_values("school_year")
        rows = dataframe_to_records(grp.rename(columns={"needs_count": "needs_support"}))
        return {"rows": rows}
    except Exception:
        logger.exception("get_support_trend failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics/assessment-averages")
def get_assessment_averages(
    subject: str | None = None,
    school_year: str | None = None,
    grade_level: str | None = None,
):
    """
    Assessment-type averages across school (score_normalized).

    Used by Analytics page's "Assessment type averages across school" chart.
    Optional grade_level filters to assessments for that grade (via student_enrollments).
    """
    conn = get_db_connection()
    try:
        params: list = []
        if grade_level:
            query = """
                SELECT a.subject_area,
                       a.assessment_type,
                       AVG(a.score_normalized) AS average_score,
                       COUNT(*) AS count
                FROM assessments a
                JOIN student_enrollments e ON e.enrollment_id = a.enrollment_id
                WHERE a.score_normalized IS NOT NULL
                  AND e.grade_level = %s
            """
            params.append(grade_level)
        else:
            query = """
                SELECT subject_area,
                       assessment_type,
                       AVG(score_normalized) AS average_score,
                       COUNT(*) AS count
                FROM assessments
                WHERE score_normalized IS NOT NULL
            """
        if subject:
            query += " AND a.subject_area = %s" if grade_level else " AND subject_area = %s"
            params.append(subject)
        if school_year:
            query += " AND a.school_year = %s" if grade_level else " AND school_year = %s"
            params.append(school_year)
        query += " GROUP BY a.subject_area, a.assessment_type ORDER BY a.subject_area, a.assessment_type" if grade_level else " GROUP BY subject_area, assessment_type ORDER BY subject_area, assessment_type"
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        conn.close()
        logger.exception("get_assessment_averages failed")
        raise HTTPException(status_code=500, detail="Internal server error")
    conn.close()
    if df is None or df.empty:
        return {"rows": []}
    df["average_score"] = df["average_score"].round(1)
    rows = dataframe_to_records(df)
    return {"rows": rows}


@router.get("/metrics/erb-comparison")
def get_erb_comparison(
    subject: str | None = None,
    school_year: str | None = None,
):
    """
    ERB vs Independent Norm comparison.

    Aggregates ERB stanine/percentile by grade and subtest, and compares to Independent Norm
    (via core.erb_scoring.get_erb_independent_norm). Used by the Analytics page.
    """
    conn = get_db_connection()
    try:
        # Restrict ERB subtests by subject if provided (Math: ERB_Mathematics; Reading: others).
        if subject and str(subject).strip().lower() == "math":
            subtests = ["ERB_Mathematics"]
        elif subject and str(subject).strip().lower() == "reading":
            subtests = [s for s in ERB_SUBTESTS if s != "ERB_Mathematics"]
        else:
            subtests = list(ERB_SUBTESTS)

        params: list = [subtests]
        query = """
            SELECT a.student_id,
                   a.school_year,
                   a.assessment_type,
                   a.score_value,
                   s.grade_level
            FROM assessments a
            JOIN students s ON a.student_id = s.student_id AND a.school_year = s.school_year
            WHERE a.assessment_type = ANY(%s)
        """
        if subject:
            query += " AND a.subject_area = %s"
            params.append(subject)
        if school_year:
            query += " AND a.school_year = %s"
            params.append(school_year)
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        conn.close()
        logger.exception("get_erb_comparison failed")
        raise HTTPException(status_code=500, detail="Internal server error")
    conn.close()

    if df is None or df.empty:
        return {"rows": []}

    # Parse ERB scores into stanine/percentile
    rows = []
    for _, row in df.iterrows():
        parsed = parse_erb_score_value(row.get("score_value", ""))
        stanine = parsed.get("stanine")
        if stanine is None:
            continue
        pct = parsed.get("percentile") or 50
        rows.append(
            {
                "grade_level": row["grade_level"],
                "subtest": row["assessment_type"],
                "stanine": stanine,
                "percentile": pct,
            }
        )
    if not rows:
        return {"rows": []}

    erb_agg = pd.DataFrame(rows)
    our_avg = (
        erb_agg.groupby(["grade_level", "subtest"])
        .agg(our_stanine=("stanine", "mean"), our_percentile=("percentile", "mean"))
        .reset_index()
    )

    norm_rows = []
    for _, r in our_avg.iterrows():
        grade = r["grade_level"]
        subtest = r["subtest"]
        norm = get_erb_independent_norm(grade, subtest)
        our_stanine = float(r["our_stanine"])
        our_pct = float(r["our_percentile"])
        norm_rows.append(
            {
                "grade_level": grade,
                "subtest": subtest,
                "subtest_label": ERB_SUBTEST_LABELS.get(subtest, subtest),
                "our_avg_stanine": round(our_stanine, 1),
                "ind_avg_stanine": norm["avg_stanine"],
                "diff_stanine": round(our_stanine - norm["avg_stanine"], 1),
                "our_avg_percentile": round(our_pct, 1),
                "ind_avg_percentile": norm["avg_percentile"],
                "diff_percentile": round(our_pct - norm["avg_percentile"], 1),
            }
        )

    if not norm_rows:
        return {"rows": []}

    return {"rows": norm_rows}
