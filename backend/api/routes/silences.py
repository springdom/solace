"""Silence/maintenance window API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import SilenceWindow
from backend.schemas import (
    SilenceWindowCreate,
    SilenceWindowListResponse,
    SilenceWindowResponse,
    SilenceWindowUpdate,
)

router = APIRouter(prefix="/silences", tags=["silences"])


@router.get("", response_model=SilenceWindowListResponse)
async def list_silences(
    state: str = Query("all", pattern="^(all|active|expired)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List silence windows with optional state filter."""
    now = datetime.now(UTC)
    query = select(SilenceWindow)
    count_query = select(func.count(SilenceWindow.id))

    if state == "active":
        filters = [
            SilenceWindow.is_active.is_(True),
            SilenceWindow.starts_at <= now,
            SilenceWindow.ends_at >= now,
        ]
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    elif state == "expired":
        filters = [
            SilenceWindow.is_active.is_(True),
            SilenceWindow.ends_at < now,
        ]
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(SilenceWindow.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    windows = list(result.scalars().all())

    return SilenceWindowListResponse(
        windows=[SilenceWindowResponse.model_validate(w) for w in windows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SilenceWindowResponse, status_code=201)
async def create_silence(
    data: SilenceWindowCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new silence window."""
    if data.ends_at <= data.starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")

    window = SilenceWindow(
        name=data.name,
        matchers=data.matchers,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        created_by=data.created_by,
        reason=data.reason,
    )
    db.add(window)
    await db.flush()
    await db.refresh(window)
    return SilenceWindowResponse.model_validate(window)


@router.get("/{silence_id}", response_model=SilenceWindowResponse)
async def get_silence(
    silence_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single silence window."""
    stmt = select(SilenceWindow).where(SilenceWindow.id == silence_id)
    result = await db.execute(stmt)
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(404, "Silence window not found")
    return SilenceWindowResponse.model_validate(window)


@router.put("/{silence_id}", response_model=SilenceWindowResponse)
async def update_silence(
    silence_id: str,
    data: SilenceWindowUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a silence window."""
    stmt = select(SilenceWindow).where(SilenceWindow.id == silence_id)
    result = await db.execute(stmt)
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(404, "Silence window not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(window, field, value)

    # Validate time range if both are being set
    if window.ends_at <= window.starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")

    window.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(window)
    return SilenceWindowResponse.model_validate(window)


@router.delete("/{silence_id}", status_code=204)
async def delete_silence(
    silence_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a silence window (set is_active=False)."""
    stmt = select(SilenceWindow).where(SilenceWindow.id == silence_id)
    result = await db.execute(stmt)
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(404, "Silence window not found")

    window.is_active = False
    window.updated_at = datetime.now(UTC)
    await db.flush()
