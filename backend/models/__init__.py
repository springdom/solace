import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

# ─── Enums ───────────────────────────────────────────────


class AlertStatus(enum.StrEnum):
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ARCHIVED = "archived"


class Severity(enum.StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    LOW = "low"
    INFO = "info"


class IncidentStatus(enum.StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


# ─── User ───────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=UserRole.VIEWER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
    )

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role.value}]>"


# ─── Alert ───────────────────────────────────────────────


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_instance: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=AlertStatus.FIRING,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=Severity.WARNING,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    service: Mapped[str | None] = mapped_column(String(255))
    environment: Mapped[str | None] = mapped_column(String(100))
    host: Mapped[str | None] = mapped_column(String(255))
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    annotations: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1)
    generator_url: Mapped[str | None] = mapped_column(Text)
    runbook_url: Mapped[str | None] = mapped_column(Text)
    ticket_url: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Relationships ────────────────────────────────────
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id")
    )
    incident: Mapped["Incident | None"] = relationship(back_populates="alerts")
    notes: Mapped[list["AlertNote"]] = relationship(
        back_populates="alert", order_by="AlertNote.created_at.desc()",
        cascade="all, delete-orphan",
    )
    occurrences: Mapped[list["AlertOccurrence"]] = relationship(
        back_populates="alert", order_by="AlertOccurrence.received_at.desc()",
        cascade="all, delete-orphan",
    )

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ── Indexes ──────────────────────────────────────────
    __table_args__ = (
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_service", "service"),
        Index("idx_alerts_created_at", "created_at"),
        Index("idx_alerts_fingerprint_status", "fingerprint", "status"),
        Index("idx_alerts_labels", "labels", postgresql_using="gin"),
        Index("idx_alerts_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Alert {self.name} [{self.severity.value}] {self.status.value}>"


# ─── Alert Note ──────────────────────────────────────────


class AlertNote(Base):
    __tablename__ = "alert_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))

    # ── Relationships ────────────────────────────────────
    alert: Mapped["Alert"] = relationship(back_populates="notes")

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_alert_notes_alert_id", "alert_id"),
        Index("idx_alert_notes_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AlertNote {str(self.id)[:8]} on alert {str(self.alert_id)[:8]}>"


# ─── Alert Occurrence (Duplicate Timeline) ────────────────


class AlertOccurrence(Base):
    __tablename__ = "alert_occurrences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────
    alert: Mapped["Alert"] = relationship(back_populates="occurrences")

    __table_args__ = (
        Index("idx_alert_occurrences_alert_id", "alert_id"),
        Index("idx_alert_occurrences_received_at", "received_at"),
    )

    def __repr__(self) -> str:
        return f"<AlertOccurrence {str(self.alert_id)[:8]} at {self.received_at}>"


# ─── Incident ────────────────────────────────────────────


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=IncidentStatus.OPEN,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=Severity.WARNING,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    phase: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # ── Relationships ────────────────────────────────────
    alerts: Mapped[list["Alert"]] = relationship(back_populates="incident")
    events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident", order_by="IncidentEvent.created_at"
    )

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_incidents_status", "status"),
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<Incident {self.title} [{self.status.value}]>"


# ─── Incident Event (Audit Trail) ────────────────────────


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255))
    event_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # ── Relationships ────────────────────────────────────
    incident: Mapped["Incident"] = relationship(back_populates="events")

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<IncidentEvent {self.event_type} on {self.incident_id}>"


# ─── Integration (Configured alert sources) ──────────────


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)  # generic, prometheus, etc
    api_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Integration {self.name} ({self.provider})>"


# ─── Silence Window (Maintenance Windows) ─────────────────


class SilenceWindow(Base):
    __tablename__ = "silence_windows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    matchers: Mapped[dict] = mapped_column(JSONB, default=dict)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_silence_windows_active", "is_active", "starts_at", "ends_at"),
    )

    def __repr__(self) -> str:
        return f"<SilenceWindow {self.name} ({self.starts_at} - {self.ends_at})>"


# ─── Notification Channel ────────────────────────────────


class ChannelType(enum.StrEnum):
    SLACK = "slack"
    EMAIL = "email"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    logs: Mapped[list["NotificationLog"]] = relationship(back_populates="channel")

    def __repr__(self) -> str:
        return f"<NotificationChannel {self.name} ({self.channel_type.value})>"


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notification_channels.id"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    channel: Mapped["NotificationChannel"] = relationship(back_populates="logs")

    __table_args__ = (
        Index("idx_notification_logs_channel_incident", "channel_id", "incident_id"),
        Index("idx_notification_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog {self.event_type} [{self.status.value}]>"


# ─── On-Call Models (re-exported) ─────────────────────────
# Imported after all base models are defined to avoid circular deps

from backend.models.oncall import EscalationPolicy as EscalationPolicy  # noqa: E402
from backend.models.oncall import OnCallOverride as OnCallOverride  # noqa: E402
from backend.models.oncall import OnCallSchedule as OnCallSchedule  # noqa: E402
from backend.models.oncall import RotationType as RotationType  # noqa: E402
from backend.models.oncall import ServiceEscalationMapping as ServiceEscalationMapping  # noqa: E402
