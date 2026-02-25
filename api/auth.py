"""
Clerk JWT authentication for FastAPI.

Validates session tokens issued by Clerk using their JWKS endpoint.
Extracts user identity, organization (school), and role from JWT claims.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)

_JWKS_CACHE_TTL = 3600  # re-fetch signing keys every hour
_jwks_client: Optional[PyJWKClient] = None
_jwks_client_init_time: float = 0


def _get_jwks_client() -> PyJWKClient:
    """Lazily create (and periodically refresh) the JWKS client."""
    global _jwks_client, _jwks_client_init_time

    now = time.time()
    if _jwks_client is None or (now - _jwks_client_init_time) > _JWKS_CACHE_TTL:
        issuer = os.environ.get("CLERK_JWT_ISSUER", "").rstrip("/")
        if not issuer:
            raise RuntimeError("CLERK_JWT_ISSUER environment variable is not set")
        jwks_url = f"{issuer}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        _jwks_client_init_time = now
        logger.info("JWKS client initialized from %s", jwks_url)

    return _jwks_client


@dataclass
class CurrentUser:
    """Authenticated user context extracted from a Clerk JWT."""

    user_id: str
    org_id: Optional[str] = None
    org_role: Optional[str] = None
    org_slug: Optional[str] = None
    email: Optional[str] = None
    session_id: Optional[str] = None


def _extract_bearer_token(request: Request) -> str:
    """Pull the token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth[7:]


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: validate Clerk JWT and return the authenticated user."""
    token = _extract_bearer_token(request)

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)

        issuer = os.environ.get("CLERK_JWT_ISSUER", "").rstrip("/")
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    except (jwt.InvalidTokenError, PyJWKClientError) as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return CurrentUser(
        user_id=payload["sub"],
        org_id=payload.get("org_id"),
        org_role=payload.get("org_role"),
        org_slug=payload.get("org_slug"),
        email=payload.get("email"),
        session_id=payload.get("sid"),
    )


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency: require the authenticated user to have an admin role."""
    if user.org_role not in ("org:admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
