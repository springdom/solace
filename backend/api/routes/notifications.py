"""Notification channel management API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import (
    ChannelType,
    Incident,
    NotificationChannel,
    NotificationLog,
)
from backend.schemas import (
    NotificationChannelCreate,
    NotificationChannelListResponse,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationLogListResponse,
    NotificationLogResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ─── Channels ─────────────────────────────────────────────


@router.get("/channels", response_model=NotificationChannelListResponse)
async def list_channels(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all notification channels."""
    count_result = await db.execute(select(func.count(NotificationChannel.id)))
    total = count_result.scalar() or 0

    query = (
        select(NotificationChannel)
        .order_by(NotificationChannel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    channels = list(result.scalars().all())

    return NotificationChannelListResponse(
        channels=[NotificationChannelResponse.model_validate(c) for c in channels],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new notification channel."""
    try:
        channel_type = ChannelType(data.channel_type)
    except ValueError:
        valid = ", ".join(f"'{t.value}'" for t in ChannelType)
        raise HTTPException(
            400,
            f"Invalid channel_type: {data.channel_type}. Must be one of: {valid}",
        )

    # Validate config based on type
    if channel_type == ChannelType.SLACK and not data.config.get("webhook_url"):
        raise HTTPException(400, "Slack channels require 'webhook_url' in config")
    if channel_type == ChannelType.EMAIL and not data.config.get("recipients"):
        raise HTTPException(400, "Email channels require 'recipients' list in config")
    if channel_type == ChannelType.TEAMS and not data.config.get("webhook_url"):
        raise HTTPException(400, "Teams channels require 'webhook_url' in config")
    if channel_type == ChannelType.WEBHOOK and not data.config.get("webhook_url"):
        raise HTTPException(400, "Webhook channels require 'webhook_url' in config")
    if channel_type == ChannelType.PAGERDUTY and not data.config.get("routing_key"):
        raise HTTPException(400, "PagerDuty channels require 'routing_key' in config")

    channel = NotificationChannel(
        name=data.name,
        channel_type=channel_type,
        config=data.config,
        filters=data.filters,
    )
    db.add(channel)
    await db.flush()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.get("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def get_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single notification channel."""
    stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")
    return NotificationChannelResponse.model_validate(channel)


@router.put("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: str,
    data: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a notification channel."""
    stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)

    channel.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a notification channel (set is_active=False)."""
    stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    channel.is_active = False
    channel.updated_at = datetime.now(UTC)
    await db.flush()


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification through a channel."""
    stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    # Find a recent incident to use as test data, eagerly load alerts
    stmt = (
        select(Incident)
        .options(selectinload(Incident.alerts))
        .order_by(Incident.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    incident = result.unique().scalar_one_or_none()

    if not incident:
        return {"status": "error", "message": "No incidents available for test notification"}

    try:
        from backend.core.notifications import _SENDERS
        sender = _SENDERS.get(channel.channel_type)
        if not sender:
            return {"status": "error", "message": f"Unknown channel type: {channel.channel_type}"}
        await sender(channel, incident, "incident_created")
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── Logs ─────────────────────────────────────────────────


@router.get("/logs", response_model=NotificationLogListResponse)
async def list_logs(
    channel_id: str | None = Query(None),
    incident_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List notification logs with optional filters."""
    query = select(NotificationLog)
    count_query = select(func.count(NotificationLog.id))

    if channel_id:
        query = query.where(NotificationLog.channel_id == channel_id)
        count_query = count_query.where(NotificationLog.channel_id == channel_id)
    if incident_id:
        query = query.where(NotificationLog.incident_id == incident_id)
        count_query = count_query.where(NotificationLog.incident_id == incident_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(NotificationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    logs = list(result.scalars().all())

    return NotificationLogListResponse(
        logs=[NotificationLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )
