import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Alert
from backend.schemas import (
    AlertAckRequest,
    AlertListResponse,
    AlertResponse,
)
from backend.services import acknowledge_alert, get_alerts, resolve_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


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
