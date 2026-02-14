import re
import uuid
from datetime import datetime
from enum import StrEnum
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator, model_validator

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


class AlertRunbookUpdate(BaseModel):
    """Set or update the runbook URL on an alert."""

    runbook_url: str = Field(..., max_length=2000, description="Runbook URL")
    create_rule: bool = Field(
        default=False,
        description="Also create a runbook rule from this alert's service/name",
    )


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


# ─── Auth ─────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    display_name: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=255)
    role: str = Field(default="user")


class UserUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


# ─── On-Call Schedules ────────────────────────────────────


class OnCallMemberSchema(BaseModel):
    """A member in an on-call rotation."""
    user_id: uuid.UUID
    order: int = Field(ge=0)


class OnCallScheduleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    timezone: str = Field(default="UTC", max_length=100)
    rotation_type: str = Field(default="weekly")
    members: list[OnCallMemberSchema] = Field(default_factory=list)
    handoff_time: str = Field(default="09:00", max_length=5)
    rotation_interval_days: int = Field(default=7, ge=1, le=365)
    rotation_interval_hours: int | None = Field(default=None, ge=1, le=720)
    effective_from: datetime | None = None
    is_active: bool = True

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @field_validator("handoff_time")
    @classmethod
    def validate_handoff_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("handoff_time must be in HH:MM format")
        h, m = int(v[:2]), int(v[3:])
        if h > 23 or m > 59:
            raise ValueError("handoff_time hours must be 0-23 and minutes 0-59")
        return v

    @field_validator("rotation_type")
    @classmethod
    def validate_rotation_type(cls, v: str) -> str:
        valid = {"hourly", "daily", "weekly", "custom"}
        if v not in valid:
            raise ValueError(f"rotation_type must be one of: {', '.join(sorted(valid))}")
        return v

    @model_validator(mode="after")
    def validate_interval_for_type(self) -> "OnCallScheduleCreate":
        if self.rotation_type == "hourly" and not self.rotation_interval_hours:
            self.rotation_interval_hours = 1
        return self


class OnCallScheduleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    timezone: str | None = None
    rotation_type: str | None = None
    members: list[OnCallMemberSchema] | None = None
    handoff_time: str | None = None
    rotation_interval_days: int | None = None
    rotation_interval_hours: int | None = Field(default=None, ge=1, le=720)
    is_active: bool | None = None


class OnCallOverrideResponse(BaseModel):
    id: uuid.UUID
    schedule_id: uuid.UUID
    user_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OnCallScheduleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    timezone: str
    rotation_type: str
    members: list[dict] = []
    handoff_time: str
    rotation_interval_days: int
    rotation_interval_hours: int | None = None
    effective_from: datetime
    is_active: bool
    overrides: list[OnCallOverrideResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnCallScheduleListResponse(BaseModel):
    schedules: list[OnCallScheduleResponse]
    total: int


class OnCallCurrentResponse(BaseModel):
    schedule_id: uuid.UUID
    schedule_name: str
    user: UserResponse | None = None


class OnCallOverrideCreate(BaseModel):
    user_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "OnCallOverrideCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


# ─── Escalation Policies ─────────────────────────────────


class EscalationTargetSchema(BaseModel):
    """A single escalation target — a user or on-call schedule."""
    type: str = Field(..., description="Target type: 'user' or 'schedule'")
    id: uuid.UUID

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("user", "schedule"):
            raise ValueError("target type must be 'user' or 'schedule'")
        return v


class EscalationLevelSchema(BaseModel):
    """A single escalation level within a policy."""
    level: int = Field(..., ge=1)
    targets: list[EscalationTargetSchema] = Field(default_factory=list)
    timeout_minutes: int = Field(default=15, ge=1, le=1440)


class EscalationPolicyCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    repeat_count: int = Field(default=0, ge=0, le=10)
    levels: list[EscalationLevelSchema] = Field(default_factory=list)


class EscalationPolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repeat_count: int | None = Field(default=None, ge=0, le=10)
    levels: list[EscalationLevelSchema] | None = None


class EscalationPolicyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    repeat_count: int = 0
    levels: list[dict] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    policies: list[EscalationPolicyResponse]
    total: int


# ─── Service Escalation Mappings ──────────────────────────


class ServiceMappingCreate(BaseModel):
    service_pattern: str = Field(..., max_length=255)
    severity_filter: list[str] | None = None
    escalation_policy_id: uuid.UUID
    priority: int = Field(default=0, ge=0, le=1000)


class ServiceMappingResponse(BaseModel):
    id: uuid.UUID
    service_pattern: str
    severity_filter: list[str] | None = None
    escalation_policy_id: uuid.UUID
    priority: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Runbook Rules ───────────────────────────────────────


class RunbookRuleCreate(BaseModel):
    service_pattern: str = Field(
        ..., max_length=255,
        description="Glob pattern for service name (e.g. 'billing-*', '*')",
    )
    name_pattern: str | None = Field(
        default=None, max_length=255,
        description="Optional glob pattern for alert name",
    )
    runbook_url_template: str = Field(
        ..., max_length=2000,
        description="URL template with {service}, {host}, {name}, {environment} variables",
    )
    description: str | None = Field(default=None, max_length=500)
    priority: int = Field(default=0, ge=0, le=1000, description="Lower = evaluated first")
    is_active: bool = True


class RunbookRuleUpdate(BaseModel):
    service_pattern: str | None = Field(default=None, max_length=255)
    name_pattern: str | None = Field(default=None, max_length=255)
    runbook_url_template: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=500)
    priority: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None


class RunbookRuleResponse(BaseModel):
    id: uuid.UUID
    service_pattern: str
    name_pattern: str | None = None
    runbook_url_template: str
    description: str | None = None
    priority: int = 0
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunbookRuleListResponse(BaseModel):
    rules: list[RunbookRuleResponse]
    total: int
