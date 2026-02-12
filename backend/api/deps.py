"""Shared API dependencies (auth, etc.)."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.config import get_settings

settings = get_settings()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Validate the API key from the X-API-Key header.

    In development mode with the default secret key, auth is skipped
    to avoid friction during local development.
    """
    # Skip auth in dev mode when using the default placeholder key
    if settings.is_dev and settings.api_key == "":
        return "dev"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
