from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import Alert, AlertStatus

settings = get_settings()


async def find_duplicate(
    db: AsyncSession,
    fingerprint: str,
) -> Alert | None:
    """Find an existing active alert with the same fingerprint within the dedup window.

    An alert is considered a duplicate if:
    1. Same fingerprint (same source + name + service + host + labels)
    2. Status is FIRING or ACKNOWLEDGED (not resolved/suppressed)
    3. Was last received within the dedup time window

    Returns the existing alert if found, None otherwise.
    """
    window_start = datetime.now(UTC) - timedelta(seconds=settings.dedup_window_seconds)

    stmt = (
        select(Alert)
        .where(
            and_(
                Alert.fingerprint == fingerprint,
                Alert.status.in_([AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]),
                Alert.last_received_at >= window_start,
            )
        )
        .order_by(Alert.created_at.desc())
        .limit(1)
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def process_duplicate(
    db: AsyncSession,
    existing: Alert,
) -> Alert:
    """Update an existing alert when a duplicate is received.

    Increments the duplicate count and updates the last_received_at timestamp.
    This keeps the original alert record while tracking how many times
    the same issue has fired.
    """
    existing.duplicate_count += 1
    existing.last_received_at = datetime.now(UTC)
    existing.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(existing)
    return existing
