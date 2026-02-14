"""User management API routes (admin only)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import AuthContext, require_role
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import (
    ResetPasswordRequest,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from backend.services.users import (
    create_user,
    delete_user,
    get_users,
    reset_user_password,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse, summary="List all users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all users (admin only)."""
    users, total = await get_users(db, page=page, page_size=page_size)
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.post("", response_model=UserResponse, status_code=201, summary="Create a user")
async def create_user_route(
    body: UserCreate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account (admin only)."""
    display_name = body.display_name or body.username
    try:
        user = await create_user(
            db,
            email=body.email,
            username=body.username,
            password=body.password,
            display_name=display_name,
            role=body.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse, summary="Update a user")
async def update_user_route(
    user_id: uuid.UUID,
    body: UserUpdate,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user's profile, role, or active status (admin only)."""
    try:
        user = await update_user(db, str(user_id), **body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserResponse,
    summary="Reset user password",
)
async def reset_password_route(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Reset a user's password (admin only)."""
    user = await reset_user_password(db, str(user_id), body.new_password)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204, summary="Delete a user")
async def delete_user_route(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a user account (admin only). Cannot delete yourself."""
    if auth.user_id and str(user_id) == auth.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    success = await delete_user(db, str(user_id))
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
