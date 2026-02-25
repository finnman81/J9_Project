"""
FastAPI application for School Assessment System.

Dev:  uvicorn api.main:app --reload
Prod: gunicorn api.main:app -k uvicorn.workers.UvicornWorker (see Dockerfile)
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

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import get_current_user
from api.routers import assessments, dashboard, interventions, metrics, students, teacher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
_ENV = os.environ.get("APP_ENV", "development").lower()
_is_production = _ENV in ("production", "prod")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_cors_raw = os.environ.get("CORS_ORIGINS", "").strip()

if _is_production and not _cors_raw:
    raise RuntimeError(
        "CORS_ORIGINS must be set in production (comma-separated allowlist). "
        "Example: CORS_ORIGINS=https://app.yourschool.com"
    )

if _is_production and not os.environ.get("CLERK_JWT_ISSUER"):
    raise RuntimeError(
        "CLERK_JWT_ISSUER must be set in production. "
        "Example: CLERK_JWT_ISSUER=https://your-instance.clerk.accounts.dev"
    )

if _cors_raw:
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
    logger.info("CORS_ORIGINS not set — using dev defaults: %s", CORS_ORIGINS)

ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

app = FastAPI(
    title="School Assessment System API",
    description="API for literacy and math assessment tracking",
    version="1.0.0",
    docs_url="/docs" if not _is_production else None,
    redoc_url="/redoc" if not _is_production else None,
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

# All /api routes require a valid Clerk JWT.  The /health endpoint stays public.
_auth = [Depends(get_current_user)]

app.include_router(students.router, prefix="/api", tags=["students"], dependencies=_auth)
app.include_router(assessments.router, prefix="/api", tags=["assessments"], dependencies=_auth)
app.include_router(interventions.router, prefix="/api", tags=["interventions"], dependencies=_auth)
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"], dependencies=_auth)
app.include_router(teacher.router, prefix="/api", tags=["teacher"], dependencies=_auth)
app.include_router(metrics.router, prefix="/api", tags=["metrics"], dependencies=_auth)


@app.get("/health")
def health():
    return {"status": "ok"}
