"""
FastAPI application for School Assessment System.
Run from project root: uvicorn api.main:app --reload
"""
import sys
from pathlib import Path

# Ensure project root is on path when running as uvicorn api.main:app
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env from project root so DATABASE_URL is set without exporting in shell
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import students, assessments, interventions, dashboard, teacher, metrics

app = FastAPI(
    title="School Assessment System API",
    description="API for literacy and math assessment tracking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(students.router, prefix="/api", tags=["students"])
app.include_router(assessments.router, prefix="/api", tags=["assessments"])
app.include_router(interventions.router, prefix="/api", tags=["interventions"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(teacher.router, prefix="/api", tags=["teacher"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])


@app.get("/health")
def health():
    return {"status": "ok"}
