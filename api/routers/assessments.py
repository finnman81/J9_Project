from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.database import add_assessment, get_student_id
from core.calculations import process_assessment_score
from core.math_calculations import process_math_assessment_score
from core.utils import recalculate_literacy_scores, recalculate_math_scores

router = APIRouter()


class AddAssessmentBody(BaseModel):
    student_id: int
    assessment_type: str
    assessment_period: str
    school_year: str
    score_value: str | None = None
    score_normalized: float | None = None
    assessment_date: str | None = None
    notes: str | None = None
    concerns: str | None = None
    subject_area: str = "Reading"
    raw_score: float | None = None
    scaled_score: float | None = None


@router.post("/assessments")
def post_assessment(body: AddAssessmentBody):
    add_assessment(
        student_id=body.student_id,
        assessment_type=body.assessment_type,
        assessment_period=body.assessment_period,
        school_year=body.school_year,
        score_value=body.score_value,
        score_normalized=body.score_normalized,
        assessment_date=body.assessment_date,
        notes=body.notes,
        concerns=body.concerns,
        subject_area=body.subject_area,
        raw_score=body.raw_score,
        scaled_score=body.scaled_score,
    )
    if body.subject_area == "Reading":
        recalculate_literacy_scores(student_id=body.student_id, school_year=body.school_year)
    else:
        recalculate_math_scores(student_id=body.student_id, school_year=body.school_year)
    return {"ok": True}
