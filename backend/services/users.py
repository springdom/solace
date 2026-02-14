"""User management service functions."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import hash_password
from backend.models import User, UserRole


async def get_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[User], int]:
    """List all users with pagination."""
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    users = list(result.scalars().all())
    return users, total


async def create_user(
    db: AsyncSession,
    email: str,
    username: str,
    password: str,
    display_name: str,
    role: str = "viewer",
) -> User:
    """Create a new user account."""
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError(f"Email '{email}' is already in use")

    # Check for duplicate username
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise ValueError(f"Username '{username}' is already in use")

    try:
        user_role = UserRole(role)
    except ValueError:
        raise ValueError(f"Invalid role: {role}")

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        display_name=display_name,
        role=user_role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: str,
    **kwargs,
) -> User | None:
    """Update a user's profile. Only provided fields are updated."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None

    if "email" in kwargs and kwargs["email"] is not None:
        # Check uniqueness
        existing = await db.execute(
            select(User).where(User.email == kwargs["email"], User.id != uuid.UUID(user_id))
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Email '{kwargs['email']}' is already in use")
        user.email = kwargs["email"]

    if "display_name" in kwargs and kwargs["display_name"] is not None:
        user.display_name = kwargs["display_name"]

    if "role" in kwargs and kwargs["role"] is not None:
        try:
            user.role = UserRole(kwargs["role"])
        except ValueError:
            raise ValueError(f"Invalid role: {kwargs['role']}")

    if "is_active" in kwargs and kwargs["is_active"] is not None:
        user.is_active = kwargs["is_active"]

    await db.flush()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user_id: str) -> bool:
    """Deactivate a user (soft delete)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return False

    user.is_active = False
    await db.flush()
    return True


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """Permanently delete a user."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return False

    await db.delete(user)
    await db.flush()
    return True


async def reset_user_password(
    db: AsyncSession, user_id: str, new_password: str
) -> User | None:
    """Reset a user's password (admin action)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None

    user.hashed_password = hash_password(new_password)
    await db.flush()
    await db.refresh(user)
    return user
