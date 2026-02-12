"""Alert-to-incident correlation engine.

Groups related alerts into incidents using a service+name based strategy.
Alerts are correlated to an existing open incident if they share the same
service and were received within the correlation window.

Correlation strategy (rule-based, v1):
1. Match by service — alerts from the same service likely relate to the same issue
2. Time window — only correlate with incidents active within the correlation window
3. Severity promotion — incident severity is always the max of its alerts

Future enhancements:
- Topology-aware correlation (CMDB-backed service dependency graph)
- ML-based clustering (group by label similarity)
- Custom correlation rules (user-defined grouping keys)
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models import (
    Alert,
    AlertStatus,
    Incident,
    IncidentEvent,
    IncidentStatus,
    Severity,
)

logger = logging.getLogger(__name__)

# Severity ordering for promotion (higher index = more severe)
SEVERITY_ORDER = [
    Severity.INFO,
    Severity.LOW,
    Severity.WARNING,
    Severity.HIGH,
    Severity.CRITICAL,
]


def _max_severity(a: Severity, b: Severity) -> Severity:
    """Return the more severe of two severity levels."""
    a_idx = SEVERITY_ORDER.index(a) if a in SEVERITY_ORDER else 0
    b_idx = SEVERITY_ORDER.index(b) if b in SEVERITY_ORDER else 0
    return SEVERITY_ORDER[max(a_idx, b_idx)]


def _build_incident_title(alert: Alert) -> str:
    """Generate a human-readable incident title from the first alert."""
    parts = []
    if alert.service:
        parts.append(alert.service)
    parts.append(alert.name)
    if alert.host:
        parts.append(f"on {alert.host}")
    return " — ".join(parts[:2]) if alert.service else alert.name


async def find_matching_incident(
    db: AsyncSession,
    alert: Alert,
) -> Incident | None:
    """Find an existing open incident that this alert should be correlated with.

    Matching criteria:
    - Incident is OPEN or ACKNOWLEDGED (not resolved)
    - Same service as the alert
    - Incident started within the correlation window
    """
    settings = get_settings()
    window = timedelta(seconds=settings.correlation_window_seconds)
    cutoff = datetime.now(UTC) - window

    if not alert.service:
        # Can't correlate alerts without a service — they become standalone incidents
        return None

    stmt = (
        select(Incident)
        .where(
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED]),
            Incident.started_at >= cutoff,
        )
        # Join through alerts to find incidents with the same service
        .join(Incident.alerts)
        .where(Alert.service == alert.service)
        .options(selectinload(Incident.alerts))
        .order_by(Incident.started_at.desc())
        .limit(1)
    )

    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def correlate_alert(
    db: AsyncSession,
    alert: Alert,
) -> Incident:
    """Correlate an alert with an existing or new incident.

    If a matching incident exists, the alert is attached to it and the
    incident severity is promoted if needed. Otherwise, a new incident
    is created.

    Returns the incident the alert was correlated to.
    """
    # Skip correlation for already-resolved alerts
    if alert.status == AlertStatus.RESOLVED:
        return await _handle_resolved_alert(db, alert)

    # Try to find an existing incident
    incident = await find_matching_incident(db, alert)

    if incident:
        return await _attach_to_incident(db, alert, incident)
    else:
        return await _create_incident(db, alert)


async def _attach_to_incident(
    db: AsyncSession,
    alert: Alert,
    incident: Incident,
) -> Incident:
    """Attach an alert to an existing incident."""
    alert.incident_id = incident.id
    alert.updated_at = datetime.now(UTC)

    # Promote severity if this alert is more severe
    new_severity = _max_severity(incident.severity, alert.severity)
    severity_changed = new_severity != incident.severity
    if severity_changed:
        incident.severity = new_severity
        incident.updated_at = datetime.now(UTC)

    # Record event
    event = IncidentEvent(
        incident_id=incident.id,
        event_type="alert_added",
        description=f"Alert '{alert.name}' correlated to incident",
        event_data={
            "alert_id": str(alert.id),
            "alert_name": alert.name,
            "alert_severity": alert.severity.value,
            "alert_host": alert.host,
            "severity_promoted": severity_changed,
        },
    )
    db.add(event)

    if severity_changed:
        sev_event = IncidentEvent(
            incident_id=incident.id,
            event_type="severity_changed",
            description=f"Severity escalated to {new_severity.value}",
            event_data={
                "from": (
                    incident.severity.value
                    if not severity_changed
                    else SEVERITY_ORDER[SEVERITY_ORDER.index(new_severity) - 1].value
                ),
                "to": new_severity.value,
                "trigger_alert_id": str(alert.id),
            },
        )
        db.add(sev_event)

    await db.flush()
    await db.refresh(incident)
    await db.refresh(alert)

    logger.info(
        f"Alert '{alert.name}' attached to incident '{incident.title}' "
        f"(id={str(incident.id)[:8]}..., alerts={len(incident.alerts)})"
    )

    return incident


async def _create_incident(
    db: AsyncSession,
    alert: Alert,
) -> Incident:
    """Create a new incident from an alert."""
    incident = Incident(
        title=_build_incident_title(alert),
        status=IncidentStatus.OPEN,
        severity=alert.severity,
        summary=alert.description,
        started_at=alert.starts_at or datetime.now(UTC),
    )
    db.add(incident)
    await db.flush()

    # Link the alert
    alert.incident_id = incident.id
    alert.updated_at = datetime.now(UTC)

    # Record creation event
    event = IncidentEvent(
        incident_id=incident.id,
        event_type="incident_created",
        description=f"Incident created from alert '{alert.name}'",
        actor="system",
        event_data={
            "trigger_alert_id": str(alert.id),
            "alert_name": alert.name,
            "service": alert.service,
            "host": alert.host,
        },
    )
    db.add(event)

    await db.flush()
    await db.refresh(incident)
    await db.refresh(alert)

    logger.info(
        f"New incident created: '{incident.title}' "
        f"(id={str(incident.id)[:8]}..., severity={incident.severity.value})"
    )

    return incident


async def _handle_resolved_alert(
    db: AsyncSession,
    alert: Alert,
) -> Incident | None:
    """Handle an alert that arrives already resolved.

    If the alert belongs to an existing incident (via fingerprint match on
    a previously-seen alert), check if all alerts are now resolved and
    auto-resolve the incident.
    """
    if not alert.incident_id:
        return None

    stmt = (
        select(Incident)
        .where(Incident.id == alert.incident_id)
        .options(selectinload(Incident.alerts))
    )
    result = await db.execute(stmt)
    incident = result.unique().scalar_one_or_none()

    if not incident:
        return None

    # Check if all alerts in the incident are resolved
    all_resolved = all(
        a.status == AlertStatus.RESOLVED for a in incident.alerts
    )

    if all_resolved and incident.status != IncidentStatus.RESOLVED:
        now = datetime.now(UTC)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.updated_at = now

        event = IncidentEvent(
            incident_id=incident.id,
            event_type="incident_auto_resolved",
            description="All alerts resolved — incident auto-resolved",
            actor="system",
            event_data={"resolved_alert_id": str(alert.id)},
        )
        db.add(event)
        await db.flush()
        await db.refresh(incident)

        logger.info(f"Incident '{incident.title}' auto-resolved (all alerts resolved)")

    return incident
