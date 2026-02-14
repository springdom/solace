"""Authentication endpoints: login, current user, password change."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import AuthContext, require_auth
from backend.core.security import create_access_token, hash_password, verify_password
from backend.database import get_db
from backend.models import User
from backend.schemas import ChangePasswordRequest, LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate with username/password and return a JWT token."""
    # Find user by username or email
    stmt = select(User).where(
        (User.username == body.username) | (User.email == body.username),
        User.is_active.is_(True),
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    user.last_login_at = datetime.now(UTC)
    await db.flush()

    token = create_access_token(str(user.id), user.role.value)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    auth: AuthContext = Depends(require_auth),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    if not auth.user:
        raise HTTPException(status_code=401, detail="API key auth has no user profile")
    return UserResponse.model_validate(auth.user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the current user's password."""
    if not auth.user:
        raise HTTPException(status_code=400, detail="API key auth cannot change password")

    if not verify_password(body.current_password, auth.user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    auth.user.hashed_password = hash_password(body.new_password)
    auth.user.must_change_password = False
    await db.flush()

    return {"status": "ok", "message": "Password changed successfully"}
