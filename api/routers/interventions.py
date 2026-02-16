from fastapi import APIRouter
from pydantic import BaseModel

from core.database import add_intervention, get_all_interventions
from api.serializers import dataframe_to_records

router = APIRouter()


@router.get("/interventions")
def list_interventions(school_year: str | None = None):
    df = get_all_interventions(school_year=school_year)
    return {"interventions": dataframe_to_records(df)}


class AddInterventionBody(BaseModel):
    student_id: int
    intervention_type: str
    start_date: str
    end_date: str | None = None
    frequency: str | None = None
    duration_minutes: int | None = None
    status: str = "Active"
    notes: str | None = None
    subject_area: str | None = None
    focus_skill: str | None = None
    delivery_type: str | None = None
    minutes_per_week: int | None = None
    pre_score: float | None = None
    post_score: float | None = None
    pre_score_measure: str | None = None
    post_score_measure: str | None = None


@router.post("/interventions")
def post_intervention(body: AddInterventionBody):
    add_intervention(
        student_id=body.student_id,
        intervention_type=body.intervention_type,
        start_date=body.start_date,
        end_date=body.end_date,
        frequency=body.frequency,
        duration_minutes=body.duration_minutes,
        status=body.status,
        notes=body.notes,
        subject_area=body.subject_area,
        focus_skill=body.focus_skill,
        delivery_type=body.delivery_type,
        minutes_per_week=body.minutes_per_week,
        pre_score=body.pre_score,
        post_score=body.post_score,
        pre_score_measure=body.pre_score_measure,
        post_score_measure=body.post_score_measure,
    )
    return {"ok": True}
