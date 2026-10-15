"""Authentication middleware for the local CareerOS REST API.

Uses a shared secret token for Chrome extension <-> API communication.
The token is generated at first run and stored in data/.api_token.
Only connections from 127.0.0.1 are accepted.
"""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.utils.logger import get_logger

logger = get_logger("api.auth")

# ── Token management ──────────────────────────────────────────

_TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / ".api_token"

security = HTTPBearer(auto_error=False)


def generate_api_token() -> str:
    """Generate a cryptographically secure 32-byte hex token."""
    return secrets.token_hex(32)


def get_or_create_token() -> str:
    """Load token from disk or create a new one.

    The token file is stored in data/.api_token (gitignored).
    """
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _TOKEN_FILE.exists():
        token = _TOKEN_FILE.read_text().strip()
        if len(token) >= 32:
            return token

    token = generate_api_token()
    _TOKEN_FILE.write_text(token)
    _TOKEN_FILE.chmod(0o600)
    logger.info("Generated new API token -> %s", _TOKEN_FILE)
    return token


def verify_token(provided: str, stored: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(provided, stored)


# ── FastAPI dependency ────────────────────────────────────────

async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """FastAPI dependency that enforces localhost + bearer token.

    Returns the validated token on success, raises 401/403 otherwise.
    """
    # 1. Localhost-only guard
    client_host = request.client.host if request.client else "unknown"
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        logger.warning("Rejected non-local request from %s", client_host)
        raise HTTPException(status_code=403, detail="Only localhost connections are allowed")

    # 2. Token check
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")

    stored_token = get_or_create_token()
    if not verify_token(credentials.credentials, stored_token):
        logger.warning("Invalid API token from %s", client_host)
        raise HTTPException(status_code=401, detail="Invalid API token")

    return credentials.credentials
