"""Silence window matching for alert suppression.

Checks incoming alerts against active silence/maintenance windows.
If an alert matches, it should be stored with SUPPRESSED status
and skip correlation.

Matcher format (all fields optional, AND logic):
{
    "service": ["api", "web"],          # alert.service must be in list
    "severity": ["critical", "high"],   # alert.severity must be in list
    "labels": {"env": "staging"}        # all k/v must exist in alert.labels
}
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations import NormalizedAlert
from backend.models import SilenceWindow

logger = logging.getLogger(__name__)


def _matches(matchers: dict, alert: NormalizedAlert) -> bool:
    """Check if a normalized alert matches the silence window matchers.

    All specified matcher fields must match (AND logic).
    Empty/missing matcher fields match everything.
    """
    # Service matcher
    services = matchers.get("service")
    if services and isinstance(services, list):
        if not alert.service or alert.service not in services:
            return False

    # Severity matcher
    severities = matchers.get("severity")
    if severities and isinstance(severities, list):
        if not alert.severity or alert.severity not in severities:
            return False

    # Label matcher — all specified k/v pairs must exist in alert labels
    label_matchers = matchers.get("labels")
    if label_matchers and isinstance(label_matchers, dict):
        alert_labels = alert.labels or {}
        for key, value in label_matchers.items():
            if alert_labels.get(key) != value:
                return False

    return True


async def check_silence(
    db: AsyncSession,
    alert: NormalizedAlert,
) -> SilenceWindow | None:
    """Check if a normalized alert matches any active silence window.

    Returns the matching SilenceWindow if silenced, None otherwise.
    """
    now = datetime.now(UTC)

    stmt = select(SilenceWindow).where(
        SilenceWindow.is_active.is_(True),
        SilenceWindow.starts_at <= now,
        SilenceWindow.ends_at >= now,
    )
    result = await db.execute(stmt)
    windows = result.scalars().all()

    for window in windows:
        if _matches(window.matchers or {}, alert):
            logger.info(
                f"Alert '{alert.name}' silenced by window '{window.name}'"
            )
            return window

    return None
