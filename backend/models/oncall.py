"""On-call scheduling and escalation policy models."""

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


class RotationType(enum.StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class OnCallSchedule(Base):
    __tablename__ = "oncall_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    rotation_type: Mapped[RotationType] = mapped_column(
        Enum(RotationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=RotationType.WEEKLY,
    )
    members: Mapped[list] = mapped_column(
        JSONB, default=list,
    )
    handoff_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="09:00",
    )
    rotation_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7,
    )
    rotation_interval_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None,
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    overrides: Mapped[list["OnCallOverride"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="OnCallOverride.starts_at.desc()",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_oncall_schedules_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<OnCallSchedule {self.name}>"


class OnCallOverride(Base):
    __tablename__ = "oncall_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("oncall_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)

    schedule: Mapped["OnCallSchedule"] = relationship(back_populates="overrides")
    user: Mapped["User"] = relationship()  # noqa: F821

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_oncall_overrides_schedule", "schedule_id"),
        Index("idx_oncall_overrides_time", "starts_at", "ends_at"),
    )

    def __repr__(self) -> str:
        return f"<OnCallOverride schedule={self.schedule_id} user={self.user_id}>"


class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    repeat_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    levels: Mapped[list] = mapped_column(
        JSONB, default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EscalationPolicy {self.name}>"


class ServiceEscalationMapping(Base):
    __tablename__ = "service_escalation_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_pattern: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    severity_filter: Mapped[list | None] = mapped_column(JSONB)
    escalation_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("escalation_policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    policy: Mapped["EscalationPolicy"] = relationship()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_service_escalation_service", "service_pattern"),
        Index("idx_service_escalation_priority", "priority"),
    )

    def __repr__(self) -> str:
        return (
            f"<ServiceEscalationMapping {self.service_pattern} "
            f"-> {self.escalation_policy_id}>"
        )
