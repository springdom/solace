"""On-call resolution and escalation logic."""

import logging
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import User
from backend.models.oncall import (
    EscalationPolicy,
    OnCallOverride,
    OnCallSchedule,
    RotationType,
    ServiceEscalationMapping,
)

logger = logging.getLogger(__name__)


async def validate_member_ids(
    db: AsyncSession,
    members: list[dict],
) -> list[str]:
    """Validate that all user_ids in a members list exist and are active.

    Returns a list of invalid user_id strings (empty if all valid).
    """
    invalid: list[str] = []
    for member in members:
        user_id = member.get("user_id") if isinstance(member, dict) else member
        if not user_id:
            invalid.append("<missing>")
            continue
        stmt = select(User.id).where(User.id == user_id, User.is_active.is_(True))
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            invalid.append(str(user_id))
    return invalid


async def get_current_oncall(
    db: AsyncSession,
    schedule_id: str,
    at_time: datetime | None = None,
) -> User | None:
    """Determine who is currently on call for a schedule.

    Priority:
    1. Active overrides (highest priority)
    2. Rotation calculation based on effective_from + interval

    Supports hourly, daily, weekly, and custom rotation types.
    """
    now = at_time or datetime.now(UTC)

    stmt = (
        select(OnCallSchedule)
        .where(OnCallSchedule.id == schedule_id, OnCallSchedule.is_active.is_(True))
        .options(selectinload(OnCallSchedule.overrides))
    )
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    if not schedule:
        return None

    # Check active overrides first
    override_stmt = (
        select(OnCallOverride)
        .where(
            OnCallOverride.schedule_id == schedule.id,
            OnCallOverride.starts_at <= now,
            OnCallOverride.ends_at > now,
        )
        .order_by(OnCallOverride.created_at.desc())
        .limit(1)
    )
    override_result = await db.execute(override_stmt)
    override = override_result.scalar_one_or_none()

    if override:
        user_stmt = select(User).where(
            User.id == override.user_id, User.is_active.is_(True)
        )
        user_result = await db.execute(user_stmt)
        return user_result.scalar_one_or_none()

    # Calculate rotation position
    members = schedule.members or []
    if not members:
        return None

    try:
        tz = ZoneInfo(schedule.timezone)
    except (KeyError, ValueError):
        tz = ZoneInfo("UTC")

    now_in_tz = now.astimezone(tz)
    effective = schedule.effective_from.astimezone(tz)

    # Parse handoff time
    handoff_parts = (schedule.handoff_time or "09:00").split(":")
    handoff_hour = int(handoff_parts[0])
    handoff_minute = int(handoff_parts[1]) if len(handoff_parts) > 1 else 0

    # Calculate the handoff datetime for the effective date
    effective_handoff = effective.replace(
        hour=handoff_hour, minute=handoff_minute, second=0, microsecond=0
    )
    if effective > effective_handoff:
        effective_handoff += timedelta(days=1)

    # Time since effective handoff
    delta = now_in_tz - effective_handoff
    if delta.total_seconds() < 0:
        # Before the first handoff — first member is on call
        member_index = 0
    else:
        rotation_type = schedule.rotation_type

        if rotation_type == RotationType.HOURLY:
            # Hourly rotation: use rotation_interval_hours (default 1)
            interval_hours = schedule.rotation_interval_hours or 1
            total_seconds = delta.total_seconds()
            rotations = int(total_seconds // (interval_hours * 3600))
            member_index = rotations % len(members)
        else:
            # Daily, weekly, custom: use rotation_interval_days
            days_elapsed = delta.days
            if rotation_type == RotationType.DAILY:
                interval = 1
            elif rotation_type == RotationType.WEEKLY:
                interval = 7
            else:
                # Custom: use rotation_interval_days directly
                interval = schedule.rotation_interval_days or 7
            rotations = days_elapsed // interval
            member_index = int(rotations) % len(members)

    member = members[member_index]
    user_id = member.get("user_id") if isinstance(member, dict) else member

    user_stmt = select(User).where(
        User.id == user_id, User.is_active.is_(True)
    )
    user_result = await db.execute(user_stmt)
    return user_result.scalar_one_or_none()


async def resolve_escalation_targets(
    db: AsyncSession,
    policy_id: str,
    level: int,
) -> list[User]:
    """Resolve all notification targets for a given escalation level.

    Targets can be:
    - type="schedule" → resolve current on-call user from the schedule
    - type="user" → fetch user directly
    """
    stmt = select(EscalationPolicy).where(EscalationPolicy.id == policy_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        return []

    levels = policy.levels or []
    target_level = None
    for lvl in levels:
        if lvl.get("level") == level:
            target_level = lvl
            break

    if not target_level:
        return []

    users: list[User] = []
    seen_ids: set[str] = set()

    for target in target_level.get("targets", []):
        target_type = target.get("type")
        target_id = target.get("id")

        if not target_type or not target_id:
            continue

        if target_type == "schedule":
            user = await get_current_oncall(db, target_id)
            if user and str(user.id) not in seen_ids:
                seen_ids.add(str(user.id))
                users.append(user)
        elif target_type == "user":
            if target_id in seen_ids:
                continue
            user_stmt = select(User).where(
                User.id == target_id, User.is_active.is_(True)
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if user:
                seen_ids.add(str(user.id))
                users.append(user)

    return users


async def find_escalation_policy(
    db: AsyncSession,
    service: str | None,
    severity: str | None,
) -> EscalationPolicy | None:
    """Find the best matching escalation policy for a service and severity.

    Fetches all mappings ordered by priority (lower = higher priority),
    evaluates service_pattern as a glob (fnmatch), and returns the
    first match that passes the severity filter.

    Priority ordering: lower number = evaluated first.
    Pattern matching: supports fnmatch patterns (*, ?, [seq]).
    """
    if not service:
        service = "*"

    # Fetch all mappings ordered by priority (ascending = highest priority first)
    stmt = (
        select(ServiceEscalationMapping)
        .order_by(
            ServiceEscalationMapping.priority.asc(),
            ServiceEscalationMapping.created_at.asc(),
        )
    )
    result = await db.execute(stmt)
    all_mappings = list(result.scalars().all())

    for mapping in all_mappings:
        # Glob pattern matching on service name
        if not fnmatch(service, mapping.service_pattern):
            continue

        # Severity filter check
        sev_filter = mapping.severity_filter
        if sev_filter and severity and severity not in sev_filter:
            continue

        # Load the policy
        policy_stmt = select(EscalationPolicy).where(
            EscalationPolicy.id == mapping.escalation_policy_id
        )
        policy_result = await db.execute(policy_stmt)
        policy = policy_result.scalar_one_or_none()
        if policy:
            return policy

    return None
