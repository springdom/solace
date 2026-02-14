import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import String as SAString
from sqlalchemy import cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.correlation import correlate_alert
from backend.core.dedup import find_duplicate, process_duplicate
from backend.core.fingerprint import generate_fingerprint
from backend.core.silence import check_silence
from backend.integrations import NormalizedAlert
from backend.models import (
    Alert,
    AlertNote,
    AlertOccurrence,
    AlertStatus,
    Incident,
    IncidentEvent,
    IncidentStatus,
    Severity,
)

logger = logging.getLogger(__name__)


async def ingest_alert(
    db: AsyncSession,
    normalized: NormalizedAlert,
) -> tuple[Alert, bool]:
    """Process a normalized alert through the ingestion pipeline.

    Pipeline:
    1. Generate fingerprint
    2. Check for duplicates
    3. If duplicate: increment counter, update timestamp
    4. If new: create alert record

    Returns:
        Tuple of (alert, is_duplicate)
    """
    # Step 1: Generate fingerprint
    fingerprint = generate_fingerprint(
        source=normalized.source,
        name=normalized.name,
        service=normalized.service,
        host=normalized.host,
        labels=normalized.labels,
    )

    # Step 2: Check for existing duplicate
    existing = await find_duplicate(db, fingerprint)

    if existing:
        # Step 3a: Update existing alert
        updated = await process_duplicate(db, existing)

        # Record occurrence for timeline
        occurrence = AlertOccurrence(alert_id=updated.id, received_at=datetime.now(UTC))
        db.add(occurrence)
        await db.flush()

        logger.info(
            f"Duplicate alert: {normalized.name} (fingerprint={fingerprint}, "
            f"count={updated.duplicate_count})"
        )

        from backend.api.routes.ws import emit_event
        await emit_event("alert.updated", {
            "alert_id": str(updated.id),
            "duplicate_count": updated.duplicate_count,
        })

        return updated, True

    # Step 2.5: Auto-attach runbook URL if not already set
    if not normalized.runbook_url:
        from backend.services.runbook import find_matching_runbook

        resolved_url = await find_matching_runbook(
            db,
            service=normalized.service,
            name=normalized.name,
            host=normalized.host,
            environment=normalized.environment,
        )
        if resolved_url:
            normalized.runbook_url = resolved_url
            logger.info(
                f"Auto-attached runbook URL for alert '{normalized.name}': "
                f"{resolved_url}"
            )

    # Step 3b: Check silence windows
    silence = await check_silence(db, normalized)
    if silence:
        alert = Alert(
            fingerprint=fingerprint,
            source=normalized.source,
            source_instance=normalized.source_instance,
            status=AlertStatus.SUPPRESSED,
            severity=Severity(normalized.severity),
            name=normalized.name,
            description=normalized.description,
            service=normalized.service,
            environment=normalized.environment,
            host=normalized.host,
            labels=normalized.labels,
            annotations=normalized.annotations,
            tags=normalized.tags,
            raw_payload=normalized.raw_payload,
            starts_at=normalized.starts_at or datetime.now(UTC),
            ends_at=normalized.ends_at,
            generator_url=normalized.generator_url,
            runbook_url=normalized.runbook_url,
            ticket_url=normalized.ticket_url,
            last_received_at=datetime.now(UTC),
        )
        db.add(alert)
        await db.flush()
        await db.refresh(alert)
        logger.info(
            f"Alert suppressed by silence '{silence.name}': {normalized.name} "
            f"(fingerprint={fingerprint}, id={alert.id})"
        )
        return alert, False

    # Step 3c: Create new alert
    alert = Alert(
        fingerprint=fingerprint,
        source=normalized.source,
        source_instance=normalized.source_instance,
        status=AlertStatus(normalized.status),
        severity=Severity(normalized.severity),
        name=normalized.name,
        description=normalized.description,
        service=normalized.service,
        environment=normalized.environment,
        host=normalized.host,
        labels=normalized.labels,
        annotations=normalized.annotations,
        tags=normalized.tags,
        raw_payload=normalized.raw_payload,
        starts_at=normalized.starts_at or datetime.now(UTC),
        ends_at=normalized.ends_at,
        generator_url=normalized.generator_url,
        runbook_url=normalized.runbook_url,
        ticket_url=normalized.ticket_url,
        last_received_at=datetime.now(UTC),
    )

    # Handle resolved status from source
    if normalized.status == "resolved" and normalized.ends_at:
        alert.resolved_at = normalized.ends_at

    db.add(alert)
    await db.flush()
    await db.refresh(alert)

    # Record first occurrence for timeline
    occurrence = AlertOccurrence(alert_id=alert.id, received_at=datetime.now(UTC))
    db.add(occurrence)
    await db.flush()

    # Step 4: Correlate to an incident
    from backend.core.notifications import dispatch_notifications

    result = await correlate_alert(db, alert)
    incident = result.incident

    # Step 5: Dispatch notifications for significant events
    if incident and result.event_type in ("incident_created", "severity_changed"):
        await dispatch_notifications(db, incident, result.event_type)

    logger.info(
        f"New alert: {normalized.name} (fingerprint={fingerprint}, "
        f"severity={normalized.severity}, id={alert.id}"
        f"{f', incident={str(incident.id)[:8]}' if incident else ''})"
    )

    # Emit real-time events
    from backend.api.routes.ws import emit_event

    await emit_event("alert.created", {"alert_id": str(alert.id), "name": alert.name})
    if incident and result.event_type == "incident_created":
        inc_data = {"incident_id": str(incident.id), "title": incident.title}
        await emit_event("incident.created", inc_data)
    elif incident and result.event_type == "severity_changed":
        inc_data = {"incident_id": str(incident.id), "title": incident.title}
        await emit_event("incident.updated", inc_data)

    return alert, False


async def get_alerts(
    db: AsyncSession,
    status: str | None = None,
    severity: str | None = None,
    service: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Alert], int]:
    """Fetch alerts with optional filtering, search, sorting, and pagination."""
    query = select(Alert)
    count_query = select(func.count(Alert.id))

    # Apply filters
    if status:
        query = query.where(Alert.status == AlertStatus(status))
        count_query = count_query.where(Alert.status == AlertStatus(status))
    if severity:
        query = query.where(Alert.severity == Severity(severity))
        count_query = count_query.where(Alert.severity == Severity(severity))
    if service:
        query = query.where(Alert.service == service)
        count_query = count_query.where(Alert.service == service)

    # Exact tag filter (JSONB array containment)
    if tag:
        tag_filter = Alert.tags.contains([tag])
        query = query.where(tag_filter)
        count_query = count_query.where(tag_filter)

    # Text search across name, service, host, description, tags
    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Alert.name.ilike(pattern),
            Alert.service.ilike(pattern),
            Alert.host.ilike(pattern),
            Alert.description.ilike(pattern),
            Alert.fingerprint.ilike(pattern),
            cast(Alert.tags, SAString).ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting
    sort_columns = {
        "created_at": Alert.created_at,
        "severity": Alert.severity,
        "name": Alert.name,
        "service": Alert.service,
        "status": Alert.status,
        "starts_at": Alert.starts_at,
        "last_received_at": Alert.last_received_at,
        "duplicate_count": Alert.duplicate_count,
    }
    sort_col = sort_columns.get(sort_by, Alert.created_at)
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    # Apply pagination and ordering
    query = (
        query.order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    alerts = list(result.scalars().all())

    return alerts, total


async def acknowledge_alert(
    db: AsyncSession,
    alert_id: str,
    acknowledged_by: str | None = None,
) -> Alert | None:
    """Mark an alert as acknowledged."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()

    if not alert:
        return None

    now = datetime.now(UTC)
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = now
    alert.updated_at = now
    await db.flush()
    await db.refresh(alert)

    from backend.api.routes.ws import emit_event
    await emit_event("alert.updated", {"alert_id": str(alert.id), "status": "acknowledged"})

    return alert


async def resolve_alert(
    db: AsyncSession,
    alert_id: str,
) -> Alert | None:
    """Mark an alert as resolved."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()

    if not alert:
        return None

    now = datetime.now(UTC)
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now
    alert.ends_at = now
    alert.updated_at = now
    await db.flush()
    await db.refresh(alert)

    from backend.api.routes.ws import emit_event
    await emit_event("alert.updated", {"alert_id": str(alert.id), "status": "resolved"})

    return alert


# ─── Incident Services ──────────────────────────────────


async def get_incidents(
    db: AsyncSession,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "started_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Incident], int]:
    """Fetch incidents with optional filtering, search, sorting, and pagination."""
    query = select(Incident).options(selectinload(Incident.alerts))
    count_query = select(func.count(Incident.id))

    if status:
        query = query.where(Incident.status == IncidentStatus(status))
        count_query = count_query.where(Incident.status == IncidentStatus(status))

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Incident.title.ilike(pattern),
            Incident.summary.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting
    sort_columns = {
        "started_at": Incident.started_at,
        "severity": Incident.severity,
        "title": Incident.title,
        "status": Incident.status,
        "created_at": Incident.created_at,
    }
    sort_col = sort_columns.get(sort_by, Incident.started_at)
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    query = (
        query.order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    incidents = list(result.unique().scalars().all())

    return incidents, total


async def get_incident(
    db: AsyncSession,
    incident_id: str,
) -> Incident | None:
    """Fetch a single incident with alerts and events."""
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.alerts),
            selectinload(Incident.events),
        )
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def acknowledge_incident(
    db: AsyncSession,
    incident_id: str,
    acknowledged_by: str | None = None,
) -> Incident | None:
    """Acknowledge an incident and all its firing alerts."""
    incident = await get_incident(db, incident_id)
    if not incident:
        return None

    now = datetime.now(UTC)
    incident.status = IncidentStatus.ACKNOWLEDGED
    incident.acknowledged_at = now
    incident.updated_at = now

    # Acknowledge all firing alerts
    for alert in incident.alerts:
        if alert.status == AlertStatus.FIRING:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = now
            alert.updated_at = now

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="incident_acknowledged",
        description=f"Incident acknowledged{f' by {acknowledged_by}' if acknowledged_by else ''}",
        actor=acknowledged_by or "system",
        event_data={
            "alerts_acknowledged": len(
                [a for a in incident.alerts if a.acknowledged_at == now]
            )
        },
    )
    db.add(event)

    await db.flush()
    await db.refresh(incident)

    from backend.api.routes.ws import emit_event
    inc_id = str(incident.id)
    await emit_event("incident.updated", {"incident_id": inc_id, "status": "acknowledged"})

    return incident


async def resolve_incident(
    db: AsyncSession,
    incident_id: str,
    resolved_by: str | None = None,
) -> Incident | None:
    """Resolve an incident and all its active alerts."""
    incident = await get_incident(db, incident_id)
    if not incident:
        return None

    now = datetime.now(UTC)
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now
    incident.updated_at = now

    # Resolve all active alerts
    resolved_count = 0
    for alert in incident.alerts:
        if alert.status in (AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED):
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = now
            alert.ends_at = now
            alert.updated_at = now
            resolved_count += 1

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="incident_resolved",
        description=f"Incident resolved{f' by {resolved_by}' if resolved_by else ''}",
        actor=resolved_by or "system",
        event_data={"alerts_resolved": resolved_count},
    )
    db.add(event)

    await db.flush()
    await db.refresh(incident)

    from backend.api.routes.ws import emit_event
    await emit_event("incident.updated", {"incident_id": str(incident.id), "status": "resolved"})

    return incident


# ─── Alert Tags ──────────────────────────────────────────


async def update_alert_tags(
    db: AsyncSession, alert_id: str, tags: list[str]
) -> Alert | None:
    """Replace all tags on an alert."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    alert.tags = tags
    alert.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(alert)
    return alert


async def add_alert_tag(
    db: AsyncSession, alert_id: str, tag: str
) -> Alert | None:
    """Add a single tag to an alert (if not already present)."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    current_tags = list(alert.tags or [])
    if tag not in current_tags:
        current_tags.append(tag)
        alert.tags = current_tags
        alert.updated_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(alert)
    return alert


async def remove_alert_tag(
    db: AsyncSession, alert_id: str, tag: str
) -> Alert | None:
    """Remove a single tag from an alert."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    current_tags = list(alert.tags or [])
    if tag in current_tags:
        current_tags.remove(tag)
        alert.tags = current_tags
        alert.updated_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(alert)
    return alert


# ─── Alert Notes ─────────────────────────────────────────


async def get_alert_notes(
    db: AsyncSession, alert_id: str
) -> list[AlertNote]:
    """Get all notes for an alert, newest first."""
    stmt = (
        select(AlertNote)
        .where(AlertNote.alert_id == alert_id)
        .order_by(AlertNote.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_alert_note(
    db: AsyncSession, alert_id: str, text: str, author: str | None = None
) -> AlertNote:
    """Create a new note on an alert."""
    import uuid as _uuid

    # Verify alert exists
    alert_stmt = select(Alert).where(Alert.id == alert_id)
    alert_result = await db.execute(alert_stmt)
    if not alert_result.scalar_one_or_none():
        raise ValueError("Alert not found")

    note = AlertNote(alert_id=_uuid.UUID(alert_id), text=text, author=author)
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def update_alert_note(
    db: AsyncSession, note_id: str, text: str
) -> AlertNote | None:
    """Update the text of an existing note."""
    stmt = select(AlertNote).where(AlertNote.id == note_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if not note:
        return None
    note.text = text
    note.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(note)
    return note


async def delete_alert_note(
    db: AsyncSession, note_id: str
) -> bool:
    """Delete a note. Returns True if found and deleted."""
    stmt = select(AlertNote).where(AlertNote.id == note_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if not note:
        return False
    await db.delete(note)
    await db.flush()
    return True


# ─── Stats ───────────────────────────────────────────────


async def get_stats(db: AsyncSession) -> dict:
    """Get dashboard statistics: counts, MTTA, MTTR."""
    now = datetime.now(UTC)

    # Alert counts by status
    status_counts = {}
    for s in AlertStatus:
        result = await db.execute(
            select(func.count(Alert.id)).where(Alert.status == s)
        )
        status_counts[s.value] = result.scalar() or 0

    # Severity counts (active only)
    severity_counts = {}
    active_statuses = [AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]
    for sev in Severity:
        result = await db.execute(
            select(func.count(Alert.id)).where(
                Alert.status.in_(active_statuses),
                Alert.severity == sev,
            )
        )
        severity_counts[sev.value] = result.scalar() or 0

    # Incident counts by status
    incident_counts = {}
    for s in IncidentStatus:
        result = await db.execute(
            select(func.count(Incident.id)).where(Incident.status == s)
        )
        incident_counts[s.value] = result.scalar() or 0

    # MTTA: Mean Time to Acknowledge (for alerts acknowledged in last 24h)
    mtta_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Alert.acknowledged_at)
                - func.extract("epoch", Alert.starts_at)
            )
        ).where(
            Alert.acknowledged_at.is_not(None),
            Alert.acknowledged_at >= now - timedelta(hours=24),
        )
    )
    mtta_seconds = mtta_result.scalar()

    # MTTR: Mean Time to Resolve (for alerts resolved in last 24h)
    mttr_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Alert.resolved_at)
                - func.extract("epoch", Alert.starts_at)
            )
        ).where(
            Alert.resolved_at.is_not(None),
            Alert.resolved_at >= now - timedelta(hours=24),
        )
    )
    mttr_seconds = mttr_result.scalar()

    return {
        "alerts": {
            "by_status": status_counts,
            "by_severity": severity_counts,
            "total": sum(status_counts.values()),
            "active": status_counts.get("firing", 0) + status_counts.get("acknowledged", 0),
        },
        "incidents": {
            "by_status": incident_counts,
            "total": sum(incident_counts.values()),
        },
        "mtta_seconds": round(mtta_seconds, 1) if mtta_seconds else None,
        "mttr_seconds": round(mttr_seconds, 1) if mttr_seconds else None,
    }


# ─── Bulk Alert Actions ─────────────────────────────────


async def bulk_acknowledge_alerts(
    db: AsyncSession,
    alert_ids: list,
    acknowledged_by: str | None = None,
) -> list:
    """Acknowledge multiple alerts at once."""
    now = datetime.now(UTC)
    stmt = select(Alert).where(
        Alert.id.in_(alert_ids),
        Alert.status == AlertStatus.FIRING,
    )
    result = await db.execute(stmt)
    alerts = list(result.scalars().all())

    updated_ids = []
    for alert in alerts:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.updated_at = now
        updated_ids.append(alert.id)

    await db.flush()
    return updated_ids


async def bulk_resolve_alerts(
    db: AsyncSession,
    alert_ids: list,
) -> list:
    """Resolve multiple alerts at once."""
    now = datetime.now(UTC)
    stmt = select(Alert).where(
        Alert.id.in_(alert_ids),
        Alert.status.in_([AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]),
    )
    result = await db.execute(stmt)
    alerts = list(result.scalars().all())

    updated_ids = []
    for alert in alerts:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        alert.ends_at = now
        alert.updated_at = now
        updated_ids.append(alert.id)

    await db.flush()
    return updated_ids


# ─── Alert Archiving ────────────────────────────────────


async def archive_alerts(
    db: AsyncSession,
    older_than_days: int = 30,
) -> int:
    """Archive resolved alerts older than the given number of days."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=older_than_days)

    stmt = select(Alert).where(
        Alert.status == AlertStatus.RESOLVED,
        Alert.archived_at.is_(None),
        Alert.resolved_at.isnot(None),
        Alert.resolved_at < cutoff,
    )
    result = await db.execute(stmt)
    alerts = list(result.scalars().all())

    for alert in alerts:
        alert.status = AlertStatus.ARCHIVED
        alert.archived_at = now

    await db.flush()
    return len(alerts)
