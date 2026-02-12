import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ─── Enums (mirroring SQLAlchemy but for API layer) ──────


class AlertStatusEnum(StrEnum):
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class SeverityEnum(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    LOW = "low"
    INFO = "info"


class IncidentStatusEnum(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# ─── Webhook Ingestion ───────────────────────────────────


class GenericWebhookPayload(BaseModel):
    """Schema for the generic webhook endpoint.

    Accepts any JSON payload with a few required fields and
    normalizes it into Solace's internal alert format.
    """

    name: str = Field(..., description="Alert name or title", max_length=500)
    severity: SeverityEnum = Field(
        default=SeverityEnum.WARNING, description="Alert severity level"
    )
    status: AlertStatusEnum = Field(
        default=AlertStatusEnum.FIRING, description="Alert status"
    )
    description: str | None = Field(default=None, description="Human-readable description")
    service: str | None = Field(default=None, description="Affected service name", max_length=255)
    environment: str | None = Field(default=None, description="Environment (production, staging)")
    host: str | None = Field(default=None, description="Affected host/instance", max_length=255)
    labels: dict = Field(default_factory=dict, description="Arbitrary key-value labels")
    annotations: dict = Field(
        default_factory=dict, description="Additional context (runbook URL, etc)"
    )
    source: str = Field(default="generic", description="Source system identifier", max_length=100)
    source_instance: str | None = Field(default=None, description="Specific source instance URL")
    starts_at: datetime | None = Field(default=None, description="When the alert started firing")
    ends_at: datetime | None = Field(
        default=None, description="When the alert resolved (if resolved)"
    )
    generator_url: str | None = Field(
        default=None, description="URL to the source that generated this alert"
    )


# ─── Alert Responses ─────────────────────────────────────


class AlertResponse(BaseModel):
    """Alert data returned from the API."""

    id: uuid.UUID
    fingerprint: str
    source: str
    source_instance: str | None
    status: AlertStatusEnum
    severity: SeverityEnum
    name: str
    description: str | None
    service: str | None
    environment: str | None
    host: str | None
    labels: dict
    annotations: dict
    starts_at: datetime
    ends_at: datetime | None
    last_received_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    duplicate_count: int
    generator_url: str | None
    incident_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    alerts: list[AlertResponse]
    total: int
    page: int
    page_size: int


class AlertAckRequest(BaseModel):
    """Request to acknowledge an alert."""

    acknowledged_by: str | None = Field(
        default=None, description="User or system that acknowledged"
    )


# ─── Incident Responses ──────────────────────────────────


class IncidentAlertSummary(BaseModel):
    """Compact alert info shown within an incident."""

    id: uuid.UUID
    name: str
    status: AlertStatusEnum
    severity: SeverityEnum
    description: str | None = None
    service: str | None
    host: str | None
    duplicate_count: int
    starts_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: IncidentStatusEnum
    severity: SeverityEnum
    summary: str | None
    started_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    alert_count: int = 0
    alerts: list[IncidentAlertSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: IncidentStatusEnum
    severity: SeverityEnum
    summary: str | None
    started_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    alert_count: int = 0
    alerts: list[AlertResponse] = []
    events: list["IncidentEventResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""

    incidents: list[IncidentResponse]
    total: int
    page: int
    page_size: int


class IncidentEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    description: str
    actor: str | None
    event_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Integration ─────────────────────────────────────────


class IntegrationCreate(BaseModel):
    name: str = Field(..., max_length=255)
    provider: str = Field(default="generic", max_length=100)
    config: dict = Field(default_factory=dict)


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    name: str
    provider: str
    api_key: str
    is_active: bool
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Webhook Response ────────────────────────────────────


class WebhookAcceptedResponse(BaseModel):
    """Returned immediately when a webhook is received."""

    status: str = "accepted"
    alert_id: uuid.UUID
    fingerprint: str
    is_duplicate: bool = False
    duplicate_count: int = 1
    incident_id: uuid.UUID | None = None
