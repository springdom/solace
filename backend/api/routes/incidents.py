"""Incident API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import AuthContext, require_role
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import (
    AlertAckRequest,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentResponse,
)
from backend.services import (
    acknowledge_incident,
    get_incident,
    get_incidents,
    resolve_incident,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _incident_to_response(incident) -> dict:
    """Convert incident ORM to response dict with alert_count."""
    return {
        **{c.key: getattr(incident, c.key) for c in incident.__table__.columns},
        "alert_count": len(incident.alerts) if incident.alerts else 0,
        "alerts": incident.alerts if incident.alerts else [],
    }


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    status: str | None = None,
    q: str | None = None,
    sort_by: str = "started_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List incidents with optional filtering, search, and sorting."""
    incidents, total = await get_incidents(
        db, status=status, search=q, sort_by=sort_by, sort_order=sort_order,
        page=page, page_size=page_size,
    )

    return IncidentListResponse(
        incidents=[
            IncidentResponse.model_validate(_incident_to_response(inc))
            for inc in incidents
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident_detail(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single incident with full alert and event details."""
    incident = await get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    data = _incident_to_response(incident)
    data["events"] = incident.events if incident.events else []
    return IncidentDetailResponse.model_validate(data)


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
async def ack_incident(
    incident_id: str,
    body: AlertAckRequest | None = None,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge an incident and all its firing alerts."""
    incident = await acknowledge_incident(
        db,
        incident_id,
        acknowledged_by=auth.display_name,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await db.commit()
    return IncidentResponse.model_validate(_incident_to_response(incident))


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident_route(
    incident_id: str,
    auth: AuthContext = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an incident and all its active alerts."""
    incident = await resolve_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await db.commit()
    return IncidentResponse.model_validate(_incident_to_response(incident))
