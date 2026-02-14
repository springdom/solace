"""Shared API dependencies (auth, etc.)."""

import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.security import decode_token
from backend.database import get_db
from backend.models import User, UserRole

settings = get_settings()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


# ─── Auth Context ───────────────────────────────────────


class AuthContext:
    """Encapsulates the authenticated identity — either a user or API key."""

    def __init__(self, user: User | None = None, api_key: bool = False) -> None:
        self.user = user
        self.is_api_key = api_key

    @property
    def role(self) -> UserRole:
        if self.user:
            return self.user.role
        return UserRole.ADMIN  # API key gets full access (backward compat)

    @property
    def user_id(self) -> str | None:
        return str(self.user.id) if self.user else None

    @property
    def display_name(self) -> str:
        return self.user.display_name if self.user else "api-key"


# ─── Dual-mode auth (JWT + API key) ────────────────────


async def require_auth(
    api_key: str | None = Security(_api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Validate JWT Bearer token OR X-API-Key header.

    Dev mode bypass is preserved for local development.
    """
    # Dev mode bypass
    if settings.is_dev and settings.api_key == "":
        return AuthContext(api_key=True)

    # Try JWT Bearer token first
    if credentials and credentials.credentials:
        payload = decode_token(credentials.credentials)
        if payload and "sub" in payload:
            stmt = select(User).where(
                User.id == payload["sub"],
                User.is_active.is_(True),
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return AuthContext(user=user)

    # Fall back to API key
    if api_key:
        if settings.api_key and secrets.compare_digest(api_key, settings.api_key):
            return AuthContext(api_key=True)
        raise HTTPException(status_code=403, detail="Invalid API key")

    raise HTTPException(status_code=401, detail="Authentication required")


# ─── Legacy API key check (webhooks only) ──────────────


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Validate the API key from the X-API-Key header.

    In development mode with the default placeholder key, auth is skipped
    to avoid friction during local development.
    """
    if settings.is_dev and settings.api_key == "":
        return "dev"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


# ─── Role enforcement ──────────────────────────────────


def require_role(*roles: UserRole):
    """Factory: returns a dependency that enforces role membership."""
    async def _check(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return auth
    return _check
