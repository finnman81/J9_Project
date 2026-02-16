import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.database import (
    get_all_students,
    get_all_enrollments,
    get_legacy_student_uuids,
    get_enrollment,
    get_student_assessments,
    get_student_interventions,
    get_enrollment_assessments,
    get_enrollment_interventions,
    get_latest_literacy_score,
    get_latest_math_score,
    get_latest_literacy_score_for_enrollment,
    get_latest_math_score_for_enrollment,
    get_enrollment_notes,
    get_enrollment_goals,
    get_enrollment_support_status,
    get_enrollment_growth,
    create_student,
    get_student_id,
    get_enrollments_for_student_uuid,
    get_multi_enrollment_assessments,
    get_multi_enrollment_interventions,
    get_multi_enrollment_notes,
    get_multi_enrollment_goals,
    get_multi_enrollment_support_status,
    get_multi_enrollment_growth,
)
from api.serializers import dataframe_to_records, serialize_dict

router = APIRouter()


@router.get("/students")
def list_students(
    grade_level: str | None = None,
    class_name: str | None = None,
    teacher_name: str | None = None,
    school_year: str | None = None,
):
    df = get_all_students(
        grade_level=grade_level,
        class_name=class_name,
        teacher_name=teacher_name,
        school_year=school_year,
    )
    return {"students": dataframe_to_records(df)}


class CreateStudentBody(BaseModel):
    student_name: str
    grade_level: str
    class_name: str | None = None
    teacher_name: str | None = None
    school_year: str = "2024-25"


@router.post("/students")
def post_student(body: CreateStudentBody):
    student_id = create_student(
        student_name=body.student_name,
        grade_level=body.grade_level,
        class_name=body.class_name,
        teacher_name=body.teacher_name,
        school_year=body.school_year,
    )
    return {"student_id": student_id}


@router.get("/students/{student_id}")
def get_student(student_id: int):
    df = get_all_students()
    row = df[df["student_id"] == student_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Student not found")
    rec = dataframe_to_records(row)[0]
    return rec


@router.get("/students/{student_id}/assessments")
def get_student_assessments_route(student_id: int, school_year: str | None = None):
    df = get_student_assessments(student_id, school_year=school_year)
    return {"assessments": dataframe_to_records(df)}


@router.get("/students/{student_id}/interventions")
def get_student_interventions_route(student_id: int):
    df = get_student_interventions(student_id)
    return {"interventions": dataframe_to_records(df)}


@router.get("/students/{student_id}/literacy-score")
def get_student_literacy_score(student_id: int, school_year: str | None = None):
    score = get_latest_literacy_score(student_id, school_year=school_year)
    if score is None:
        return {"score": None}
    return {"score": serialize_dict(score)}


@router.get("/students/{student_id}/math-score")
def get_student_math_score(student_id: int, school_year: str | None = None):
    score = get_latest_math_score(student_id, school_year=school_year)
    if score is None:
        return {"score": None}
    return {"score": serialize_dict(score)}


# ---------------------------------------------------------------------------
# Enrollment-based endpoints (preferred for UI: stable identity + context)
# ---------------------------------------------------------------------------

@router.get("/enrollments")
def list_enrollments(
    grade_level: str | None = None,
    class_name: str | None = None,
    teacher_name: str | None = None,
    school_year: str | None = None,
):
    """List enrollments (student_enrollments + students_core). Use enrollment_id for detail links."""
    try:
        df = get_all_enrollments(
            grade_level=grade_level,
            class_name=class_name,
            teacher_name=teacher_name,
            school_year=school_year,
        )
    except Exception:
        df = get_all_students(
            grade_level=grade_level,
            class_name=class_name,
            teacher_name=teacher_name,
            school_year=school_year,
        )
        if df.empty:
            return {"enrollments": []}
        df = df.rename(columns={"student_name": "display_name"})
        df["enrollment_id"] = df["student_id"].astype(str)
        df["legacy_student_id"] = df["student_id"]
        # Add student_uuid so UI can navigate to /student/:uuid
        uuid_map = get_legacy_student_uuids(df["student_id"].dropna().astype(int).unique().tolist())
        df["student_uuid"] = df["student_id"].astype(int).map(lambda x: uuid_map.get(x))
        return {"enrollments": dataframe_to_records(df)}
    return {"enrollments": dataframe_to_records(df)}


@router.get("/enrollments/{enrollment_id}")
def get_enrollment_route(enrollment_id: str):
    """Get one enrollment by UUID. Returns display_name, grade_level, class_name, teacher_name, school_year, enrollment_id."""
    en = get_enrollment(enrollment_id)
    if not en:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {k: v for k, v in en.items() if v is not None}


@router.get("/enrollments/{enrollment_id}/assessments")
def get_enrollment_assessments_route(enrollment_id: str, school_year: str | None = None):
    df = get_enrollment_assessments(enrollment_id, school_year=school_year)
    return {"assessments": dataframe_to_records(df)}


@router.get("/enrollments/{enrollment_id}/interventions")
def get_enrollment_interventions_route(enrollment_id: str):
    df = get_enrollment_interventions(enrollment_id)
    return {"interventions": dataframe_to_records(df)}


@router.get("/enrollments/{enrollment_id}/literacy-score")
def get_enrollment_literacy_score(enrollment_id: str, school_year: str | None = None):
    score = get_latest_literacy_score_for_enrollment(enrollment_id, school_year=school_year)
    if score is None:
        return {"score": None}
    return {"score": serialize_dict(score)}


@router.get("/enrollments/{enrollment_id}/math-score")
def get_enrollment_math_score(enrollment_id: str, school_year: str | None = None):
    score = get_latest_math_score_for_enrollment(enrollment_id, school_year=school_year)
    if score is None:
        return {"score": None}
    return {"score": serialize_dict(score)}


@router.get("/enrollments/{enrollment_id}/detail")
def get_enrollment_detail(
    enrollment_id: str,
    subject: str = "Reading",
    school_year: str | None = None,
):
    """Unified student detail: header KPIs, score over time, assessments, interventions, notes, goals."""
    en = get_enrollment(enrollment_id)
    if not en:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    subject_area = "Reading" if subject.lower() == "reading" else "Math"
    support = get_enrollment_support_status(enrollment_id, subject_area)
    growth = get_enrollment_growth(enrollment_id, subject_area, school_year=school_year)
    assessments_df = get_enrollment_assessments(enrollment_id, school_year=school_year)
    interventions_df = get_enrollment_interventions(enrollment_id)
    notes_df = get_enrollment_notes(enrollment_id)
    goals_df = get_enrollment_goals(enrollment_id)

    # Header KPIs
    latest_score = support.get("latest_score") if support else None
    tier = support.get("tier") if support else None
    trend = (growth.get("trend") if growth else None) or (support.get("tier") and "Unknown")
    last_date = support.get("latest_date") if support else None
    days_since = support.get("days_since_assessment") if support else None
    has_intervention = support.get("has_active_intervention") if support else False
    goal_status = "Has goals" if goals_df is not None and not goals_df.empty else "No goals"

    # Score over time (from assessments with normalized score)
    score_col = "score_normalized"
    score_over_time = []
    if not assessments_df.empty and score_col in assessments_df.columns:
        subj = assessments_df[assessments_df["subject_area"] == subject_area] if "subject_area" in assessments_df.columns else assessments_df
        sort_cols = [c for c in ["effective_date", "assessment_date", "created_at"] if c in subj.columns]
        if sort_cols:
            subj = subj.sort_values(by=sort_cols)
        for _, row in subj.iterrows():
            s = row.get(score_col)
            if s is not None and pd.notna(s):
                period = row.get("assessment_period") or ""
                yr = row.get("school_year") or ""
                score_over_time.append({"period": f"{period} {yr}".strip(), "score": float(s)})

    return {
        "enrollment": {k: v for k, v in en.items() if v is not None},
        "header": {
            "latest_score": float(latest_score) if latest_score is not None else None,
            "tier": tier,
            "trend": trend,
            "last_assessed_date": str(last_date) if last_date else None,
            "days_since_assessment": int(days_since) if days_since is not None else None,
            "has_active_intervention": bool(has_intervention),
            "goal_status": goal_status,
        },
        "score_over_time": score_over_time,
        "assessments": dataframe_to_records(assessments_df),
        "interventions": dataframe_to_records(interventions_df),
        "notes": dataframe_to_records(notes_df),
        "goals": dataframe_to_records(goals_df),
    }


# ---------------------------------------------------------------------------
# Student detail by student_uuid (aggregated across multiple enrollments)
# ---------------------------------------------------------------------------

@router.get("/student-detail/{student_uuid}")
def get_student_detail_by_uuid(
    student_uuid: str,
    subject: str = "Reading",
    enrollment_ids: str | None = None,
):
    """
    Student detail aggregated across enrollments.
    - student_uuid: the student's UUID from students_core
    - subject: Reading or Math
    - enrollment_ids: optional comma-separated enrollment UUIDs to filter;
                      if omitted, uses ALL enrollments for the student.
    """
    all_enrollments_df = get_enrollments_for_student_uuid(student_uuid)
    if all_enrollments_df.empty:
        raise HTTPException(status_code=404, detail="No enrollments found for this student")

    all_enrollment_records = dataframe_to_records(all_enrollments_df)
    all_eids = [str(r["enrollment_id"]) for r in all_enrollment_records]

    # Filter to selected enrollment_ids if provided
    if enrollment_ids:
        selected = [eid.strip() for eid in enrollment_ids.split(",") if eid.strip()]
        selected = [eid for eid in selected if eid in all_eids]
        if not selected:
            selected = all_eids
    else:
        selected = all_eids

    subject_area = "Reading" if subject.lower() == "reading" else "Math"

    # Aggregate data across selected enrollments
    assessments_df = get_multi_enrollment_assessments(selected, subject_area=subject_area)
    interventions_df = get_multi_enrollment_interventions(selected)
    # Filter interventions by subject so Math page shows only Math interventions (exclude Reading and legacy null)
    if not interventions_df.empty and "subject_area" in interventions_df.columns:
        subj = interventions_df["subject_area"].astype(str).str.strip().str.lower()
        keep = subj == subject_area.lower()
        interventions_df = interventions_df.loc[keep]
    notes_df = get_multi_enrollment_notes(selected)
    goals_df = get_multi_enrollment_goals(selected)
    support = get_multi_enrollment_support_status(selected, subject_area)
    growth = get_multi_enrollment_growth(selected, subject_area)

    # Header KPIs: prefer deriving from assessments we return so KPIs are never blank when we have data
    latest_score = None
    last_date = None
    days_since = None
    if not assessments_df.empty and "score_normalized" in assessments_df.columns:
        subj = assessments_df.dropna(subset=["score_normalized"])
        if not subj.empty:
            sort_cols = [c for c in ["effective_date", "assessment_date", "created_at"] if c in subj.columns]
            if sort_cols:
                subj = subj.sort_values(by=sort_cols)
            last_row = subj.iloc[-1]
            latest_score = last_row.get("score_normalized")
            last_date = last_row.get("effective_date") or last_row.get("assessment_date")
            if last_date is not None:
                try:
                    from datetime import date as _date
                    d = last_date if isinstance(last_date, _date) else pd.Timestamp(last_date).date()
                    days_since = (pd.Timestamp.now().date() - d).days
                except Exception:
                    pass
    # Overlay from v_support_status when available (tier, trend, and sometimes score/date)
    if support:
        if latest_score is None:
            latest_score = support.get("latest_score")
        if last_date is None:
            last_date = support.get("latest_date")
        if days_since is None and support.get("days_since_assessment") is not None:
            days_since = support.get("days_since_assessment")
    tier = support.get("tier") if support else None
    if not tier or (isinstance(tier, str) and tier.strip().lower() == "unknown"):
        # Derive tier from latest score so Math (and Reading) always show Core/Strategic/Intensive when we have data
        if latest_score is not None:
            try:
                s = float(latest_score)
                if s < 40:
                    tier = "Intensive"
                elif s < 70:
                    tier = "Strategic"
                else:
                    tier = "Core"
            except (TypeError, ValueError):
                pass
    trend = growth.get("trend") if growth else None
    if not trend or (isinstance(trend, str) and trend.strip().lower() in ("unknown", "no data", "")):
        # Derive trend from last two scores in score_over_time when we have them
        if not assessments_df.empty and "score_normalized" in assessments_df.columns:
            subj = assessments_df.dropna(subset=["score_normalized"])
            if len(subj) >= 2:
                sort_cols = [c for c in ["effective_date", "assessment_date", "created_at"] if c in subj.columns]
                if sort_cols:
                    subj = subj.sort_values(by=sort_cols)
                last_two = subj.tail(2)
                scores = last_two["score_normalized"].tolist()
                if len(scores) == 2:
                    delta = float(scores[1]) - float(scores[0])
                    if delta >= 2:
                        trend = "Improving"
                    elif delta <= -2:
                        trend = "Declining"
                    else:
                        trend = "Stable"
    if not trend:
        trend = "Unknown" if tier else None
    has_intervention = support.get("has_active_intervention") if support else False
    if has_intervention is False and interventions_df is not None and not interventions_df.empty:
        statuses = interventions_df.get("status", pd.Series(dtype=object))
        if statuses is not None and len(statuses):
            active = any(
                s and ("active" in str(s).lower() or "progress" in str(s).lower() or "ongoing" in str(s).lower())
                for s in statuses
            )
            has_intervention = active
    goal_status = "Has goals" if goals_df is not None and not goals_df.empty else "No goals"

    header_obj = serialize_dict({
        "latest_score": float(latest_score) if latest_score is not None else None,
        "tier": tier,
        "trend": trend,
        "last_assessed_date": str(last_date) if last_date is not None else None,
        "days_since_assessment": int(days_since) if days_since is not None else None,
        "has_active_intervention": bool(has_intervention),
        "goal_status": goal_status,
    })

    # Score over time
    score_col = "score_normalized"
    score_over_time = []
    if not assessments_df.empty and score_col in assessments_df.columns:
        subj = assessments_df
        sort_cols = [c for c in ["effective_date", "assessment_date", "created_at"] if c in subj.columns]
        if sort_cols:
            subj = subj.sort_values(by=sort_cols)
        for _, row in subj.iterrows():
            s = row.get(score_col)
            if s is not None and pd.notna(s):
                period = row.get("assessment_period") or ""
                yr = row.get("school_year") or ""
                score_over_time.append({"period": f"{period} {yr}".strip(), "score": float(s)})

    # Display name from first enrollment record
    display_name = all_enrollment_records[0].get("display_name", "Unknown")

    return {
        "student_uuid": student_uuid,
        "display_name": display_name,
        "enrollments": all_enrollment_records,
        "selected_enrollment_ids": selected,
        "header": header_obj,
        "score_over_time": score_over_time,
        "assessments": dataframe_to_records(assessments_df),
        "interventions": dataframe_to_records(interventions_df),
        "notes": dataframe_to_records(notes_df),
        "goals": dataframe_to_records(goals_df),
    }
