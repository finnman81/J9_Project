"""
FastAPI application for School Assessment System.
Run from project root: uvicorn api.main:app --reload
"""
import logging
import os
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

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import students, assessments, interventions, dashboard, teacher, metrics

logger = logging.getLogger(__name__)

# CORS: allowlist from env (comma-separated); default dev origins
_cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").strip()
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else ["http://localhost:5173"]
ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

app = FastAPI(
    title="School Assessment System API",
    description="API for literacy and math assessment tracking",
    version="1.0.0",
)


def _error_detail(message: str, code: str = "error") -> dict:
    """Structured error payload for API responses."""
    return {"message": message, "code": code}


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return consistent detail shape: { message, code }."""
    detail = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        payload = detail
    else:
        payload = _error_detail(str(detail) if detail else "Error", "error")
    return JSONResponse(status_code=exc.status_code, content={"detail": payload})


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized handler: do not leak exception details to client."""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": _error_detail("Internal server error", "internal_error")},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
