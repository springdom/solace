import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Alert
from backend.schemas import (
    AlertAckRequest,
    AlertListResponse,
    AlertNoteCreate,
    AlertNoteListResponse,
    AlertNoteResponse,
    AlertNoteUpdate,
    AlertResponse,
    AlertTagsUpdate,
)
from backend.services import (
    acknowledge_alert,
    add_alert_tag,
    create_alert_note,
    delete_alert_note,
    get_alert_notes,
    get_alerts,
    remove_alert_tag,
    resolve_alert,
    update_alert_note,
    update_alert_tags,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ─── Note routes (must be before /{alert_id} to avoid UUID collision) ──


@router.put(
    "/notes/{note_id}",
    response_model=AlertNoteResponse,
    summary="Update a note",
)
async def edit_note(
    note_id: uuid.UUID,
    body: AlertNoteUpdate,
    db: AsyncSession = Depends(get_db),
) -> AlertNoteResponse:
    """Update the text of an existing note."""
    note = await update_alert_note(db, str(note_id), body.text)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return AlertNoteResponse.model_validate(note)


@router.delete(
    "/notes/{note_id}",
    status_code=204,
    summary="Delete a note",
)
async def remove_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a note."""
    deleted = await delete_alert_note(db, str(note_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")


# ─── Alert list & detail ──────────────────────────────────


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List alerts",
)
async def list_alerts(
    status: str | None = Query(default=None, description="Filter by status"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    service: str | None = Query(default=None, description="Filter by service"),
    q: str | None = Query(default=None, description="Search name, service, host, description"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """List alerts with optional filtering, search, sorting, and pagination."""
    alerts, total = await get_alerts(
        db, status=status, severity=severity, service=service,
        search=q, sort_by=sort_by, sort_order=sort_order,
        page=page, page_size=page_size,
    )

    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert by ID",
)
async def get_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Fetch a single alert by its ID."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse.model_validate(alert)


# ─── Alert actions ─────────────────────────────────────────


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge an alert",
)
async def ack_alert(
    alert_id: uuid.UUID,
    body: AlertAckRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Mark an alert as acknowledged."""
    acknowledged_by = body.acknowledged_by if body else None
    alert = await acknowledge_alert(db, str(alert_id), acknowledged_by)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse.model_validate(alert)


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve an alert",
)
async def resolve(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Mark an alert as resolved."""
    alert = await resolve_alert(db, str(alert_id))

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse.model_validate(alert)


# ─── Tags ──────────────────────────────────────────────────


@router.put(
    "/{alert_id}/tags",
    response_model=AlertResponse,
    summary="Set alert tags",
)
async def set_tags(
    alert_id: uuid.UUID,
    body: AlertTagsUpdate,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Replace all tags on an alert."""
    alert = await update_alert_tags(db, str(alert_id), body.tags)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.post(
    "/{alert_id}/tags/{tag}",
    response_model=AlertResponse,
    summary="Add a tag to an alert",
)
async def add_tag(
    alert_id: uuid.UUID,
    tag: str,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Add a single tag to an alert."""
    alert = await add_alert_tag(db, str(alert_id), tag)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.delete(
    "/{alert_id}/tags/{tag}",
    response_model=AlertResponse,
    summary="Remove a tag from an alert",
)
async def delete_tag(
    alert_id: uuid.UUID,
    tag: str,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Remove a single tag from an alert."""
    alert = await remove_alert_tag(db, str(alert_id), tag)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


# ─── Notes ─────────────────────────────────────────────────


@router.get(
    "/{alert_id}/notes",
    response_model=AlertNoteListResponse,
    summary="List alert notes",
)
async def list_notes(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AlertNoteListResponse:
    """Get all notes for an alert."""
    notes = await get_alert_notes(db, str(alert_id))
    return AlertNoteListResponse(
        notes=[AlertNoteResponse.model_validate(n) for n in notes],
        total=len(notes),
    )


@router.post(
    "/{alert_id}/notes",
    response_model=AlertNoteResponse,
    status_code=201,
    summary="Add a note to an alert",
)
async def add_note(
    alert_id: uuid.UUID,
    body: AlertNoteCreate,
    db: AsyncSession = Depends(get_db),
) -> AlertNoteResponse:
    """Add a timestamped note to an alert."""
    try:
        note = await create_alert_note(db, str(alert_id), body.text, body.author)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertNoteResponse.model_validate(note)
