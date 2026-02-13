import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ─── Enums (mirroring SQLAlchemy but for API layer) ──────


class AlertStatusEnum(StrEnum):
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ARCHIVED = "archived"


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
    tags: list[str] = Field(
        default_factory=list, description="Simple string tags for categorization"
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
    runbook_url: str | None = Field(
        default=None, description="Link to runbook for this alert"
    )
    ticket_url: str | None = Field(
        default=None, description="Link to external ticket (Jira, etc)"
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
    tags: list[str] = []
    raw_payload: dict | None = None
    starts_at: datetime
    ends_at: datetime | None
    last_received_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    duplicate_count: int
    generator_url: str | None
    runbook_url: str | None = None
    ticket_url: str | None = None
    archived_at: datetime | None = None
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


# ─── Alert Tags ─────────────────────────────────────────


class AlertTagsUpdate(BaseModel):
    """Set the full list of tags on an alert."""

    tags: list[str] = Field(..., description="Complete list of tags")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for tag in v:
            t = tag.strip()
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result


# ─── Alert Notes ────────────────────────────────────────


class AlertNoteCreate(BaseModel):
    """Create a note on an alert."""

    text: str = Field(..., min_length=1, max_length=5000, description="Note text content")
    author: str | None = Field(default=None, max_length=255, description="Author name")


class AlertNoteUpdate(BaseModel):
    """Update an existing note."""

    text: str = Field(..., min_length=1, max_length=5000)


class AlertNoteResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    text: str
    author: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertNoteListResponse(BaseModel):
    notes: list[AlertNoteResponse]
    total: int


# ─── Alert Ticket ──────────────────────────────────────────


class AlertTicketUpdate(BaseModel):
    """Set or update the external ticket URL on an alert."""

    ticket_url: str = Field(..., max_length=2000, description="External ticket URL")


# ─── Alert Occurrence History ──────────────────────────────


class AlertOccurrenceResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    received_at: datetime

    model_config = {"from_attributes": True}


class AlertOccurrenceListResponse(BaseModel):
    occurrences: list[AlertOccurrenceResponse]
    total: int


# ─── Bulk Alert Actions ────────────────────────────────────


class BulkAlertActionRequest(BaseModel):
    alert_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class BulkAlertActionResponse(BaseModel):
    updated: int
    alert_ids: list[uuid.UUID]


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
    phase: str | None = None
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
    phase: str | None = None
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


# ─── Silence Windows ───────────────────────────────────────


def _normalize_matchers(matchers: dict) -> dict:
    """Ensure matcher values like service/severity are always lists."""
    for key in ("service", "severity"):
        val = matchers.get(key)
        if isinstance(val, str):
            matchers[key] = [val]
    return matchers


class SilenceWindowCreate(BaseModel):
    name: str = Field(..., max_length=255)
    matchers: dict = Field(default_factory=dict)
    starts_at: datetime
    ends_at: datetime
    created_by: str | None = Field(default=None, max_length=255)
    reason: str | None = None

    @field_validator("matchers")
    @classmethod
    def normalize_matchers(cls, v: dict) -> dict:
        return _normalize_matchers(v)


class SilenceWindowUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    matchers: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    reason: str | None = None

    @field_validator("matchers")
    @classmethod
    def normalize_matchers(cls, v: dict | None) -> dict | None:
        if v is not None:
            return _normalize_matchers(v)
        return v


class SilenceWindowResponse(BaseModel):
    id: uuid.UUID
    name: str
    matchers: dict
    starts_at: datetime
    ends_at: datetime
    created_by: str | None
    reason: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("matchers")
    @classmethod
    def normalize_matchers(cls, v: dict) -> dict:
        return _normalize_matchers(v)


class SilenceWindowListResponse(BaseModel):
    windows: list[SilenceWindowResponse]
    total: int
    page: int
    page_size: int


# ─── Notification Channels ─────────────────────────────────


class NotificationChannelCreate(BaseModel):
    name: str = Field(..., max_length=255)
    channel_type: str = Field(..., description="slack or email")
    config: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)


class NotificationChannelUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    config: dict | None = None
    is_active: bool | None = None
    filters: dict | None = None


class NotificationChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel_type: str
    config: dict
    is_active: bool
    filters: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationChannelListResponse(BaseModel):
    channels: list[NotificationChannelResponse]
    total: int
    page: int
    page_size: int


class NotificationLogResponse(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    incident_id: uuid.UUID
    event_type: str
    status: str
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogListResponse(BaseModel):
    logs: list[NotificationLogResponse]
    total: int
    page: int
    page_size: int
