"""CRUD services for on-call schedules, escalation policies, and mappings."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.oncall import (
    EscalationPolicy,
    OnCallOverride,
    OnCallSchedule,
    ServiceEscalationMapping,
)

logger = logging.getLogger(__name__)


# ─── Schedules ─────────────────────────────────────────────


async def get_schedules(
    db: AsyncSession,
    active_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[OnCallSchedule], int]:
    """List on-call schedules with pagination."""
    query = select(OnCallSchedule).options(
        selectinload(OnCallSchedule.overrides)
    )
    count_query = select(func.count(OnCallSchedule.id))

    if active_only:
        query = query.where(OnCallSchedule.is_active.is_(True))
        count_query = count_query.where(OnCallSchedule.is_active.is_(True))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(OnCallSchedule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    schedules = list(result.unique().scalars().all())
    return schedules, total


async def get_schedule(
    db: AsyncSession, schedule_id: str
) -> OnCallSchedule | None:
    """Get a single schedule by ID."""
    stmt = (
        select(OnCallSchedule)
        .where(OnCallSchedule.id == schedule_id)
        .options(selectinload(OnCallSchedule.overrides))
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_schedule(
    db: AsyncSession, **kwargs
) -> OnCallSchedule:
    """Create a new on-call schedule."""
    schedule = OnCallSchedule(**kwargs)
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    # Re-fetch with overrides eagerly loaded for serialization
    return await get_schedule(db, str(schedule.id)) or schedule


async def update_schedule(
    db: AsyncSession, schedule_id: str, **kwargs
) -> OnCallSchedule | None:
    """Update an existing schedule."""
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        return None

    for key, value in kwargs.items():
        if hasattr(schedule, key):
            setattr(schedule, key, value)

    schedule.updated_at = datetime.now(UTC)
    await db.flush()
    # Re-fetch with overrides eagerly loaded for serialization
    return await get_schedule(db, schedule_id)


async def delete_schedule(
    db: AsyncSession, schedule_id: str
) -> bool:
    """Delete a schedule. Returns True if found and deleted."""
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        return False
    await db.delete(schedule)
    await db.flush()
    return True


# ─── Overrides ─────────────────────────────────────────────


async def create_override(
    db: AsyncSession, **kwargs
) -> OnCallOverride:
    """Create a temporary on-call override."""
    override = OnCallOverride(**kwargs)
    db.add(override)
    await db.flush()
    await db.refresh(override)
    return override


async def delete_override(
    db: AsyncSession, override_id: str
) -> bool:
    """Delete an override."""
    stmt = select(OnCallOverride).where(OnCallOverride.id == override_id)
    result = await db.execute(stmt)
    override = result.scalar_one_or_none()
    if not override:
        return False
    await db.delete(override)
    await db.flush()
    return True


# ─── Escalation Policies ──────────────────────────────────


async def get_policies(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[EscalationPolicy], int]:
    """List escalation policies with pagination."""
    count_result = await db.execute(
        select(func.count(EscalationPolicy.id))
    )
    total = count_result.scalar() or 0

    query = (
        select(EscalationPolicy)
        .order_by(EscalationPolicy.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    policies = list(result.scalars().all())
    return policies, total


async def get_policy(
    db: AsyncSession, policy_id: str
) -> EscalationPolicy | None:
    """Get a single escalation policy."""
    stmt = select(EscalationPolicy).where(EscalationPolicy.id == policy_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_policy(
    db: AsyncSession, **kwargs
) -> EscalationPolicy:
    """Create a new escalation policy."""
    policy = EscalationPolicy(**kwargs)
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


async def update_policy(
    db: AsyncSession, policy_id: str, **kwargs
) -> EscalationPolicy | None:
    """Update an existing escalation policy."""
    policy = await get_policy(db, policy_id)
    if not policy:
        return None

    for key, value in kwargs.items():
        if hasattr(policy, key):
            setattr(policy, key, value)

    policy.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(policy)
    return policy


async def delete_policy(
    db: AsyncSession, policy_id: str
) -> bool:
    """Delete an escalation policy."""
    policy = await get_policy(db, policy_id)
    if not policy:
        return False
    await db.delete(policy)
    await db.flush()
    return True


# ─── Service Escalation Mappings ──────────────────────────


async def get_mappings(
    db: AsyncSession,
) -> list[ServiceEscalationMapping]:
    """List all service-to-escalation-policy mappings, ordered by priority."""
    stmt = (
        select(ServiceEscalationMapping)
        .options(selectinload(ServiceEscalationMapping.policy))
        .order_by(
            ServiceEscalationMapping.priority.asc(),
            ServiceEscalationMapping.created_at.asc(),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_mapping(
    db: AsyncSession, **kwargs
) -> ServiceEscalationMapping:
    """Create a new service-to-policy mapping."""
    mapping = ServiceEscalationMapping(**kwargs)
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


async def delete_mapping(
    db: AsyncSession, mapping_id: str
) -> bool:
    """Delete a service-to-policy mapping."""
    stmt = select(ServiceEscalationMapping).where(
        ServiceEscalationMapping.id == mapping_id
    )
    result = await db.execute(stmt)
    mapping = result.scalar_one_or_none()
    if not mapping:
        return False
    await db.delete(mapping)
    await db.flush()
    return True
