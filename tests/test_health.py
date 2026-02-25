"""
Smoke test for the public /health endpoint. Does not require DATABASE_URL or auth.
Run with: pytest tests/test_health.py -v
"""
import pytest
from fastapi.testclient import TestClient

# Ensure project root on path before importing app
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Avoid production checks in CI (no CORS_ORIGINS / CLERK_JWT_ISSUER)
os.environ.setdefault("APP_ENV", "development")


def test_health_returns_ok():
    """GET /health returns 200 and { status: ok } without auth or DB."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
