"""Runbook rule model for automatic runbook URL attachment."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class RunbookRule(Base):
    __tablename__ = "runbook_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    name_pattern: Mapped[str | None] = mapped_column(String(255))
    runbook_url_template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_runbook_rules_service", "service_pattern"),
        Index("idx_runbook_rules_priority", "priority"),
        Index("idx_runbook_rules_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<RunbookRule {self.service_pattern} "
            f"-> {self.runbook_url_template[:50]}>"
        )
