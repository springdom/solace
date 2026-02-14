"""Improve on-call system: hourly rotation, repeat_count, mapping priority.

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2025-02-03 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add hourly rotation type to enum ──
    # PostgreSQL enums need ALTER TYPE to add values
    op.execute("ALTER TYPE rotationtype ADD VALUE IF NOT EXISTS 'hourly' BEFORE 'daily'")

    # ── Add rotation_interval_hours to oncall_schedules ──
    op.add_column(
        "oncall_schedules",
        sa.Column("rotation_interval_hours", sa.Integer, nullable=True),
    )

    # ── Replace repeat (bool) with repeat_count (int) on escalation_policies ──
    op.add_column(
        "escalation_policies",
        sa.Column(
            "repeat_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    # Migrate existing data: repeat=true → repeat_count=3 (sensible default)
    op.execute(
        "UPDATE escalation_policies SET repeat_count = CASE WHEN repeat THEN 3 ELSE 0 END"
    )
    op.drop_column("escalation_policies", "repeat")

    # ── Add priority and created_at to service_escalation_mappings ──
    op.add_column(
        "service_escalation_mappings",
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "service_escalation_mappings",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_service_escalation_priority",
        "service_escalation_mappings",
        ["priority"],
    )


def downgrade() -> None:
    # ── Revert service_escalation_mappings ──
    op.drop_index("idx_service_escalation_priority")
    op.drop_column("service_escalation_mappings", "created_at")
    op.drop_column("service_escalation_mappings", "priority")

    # ── Revert escalation_policies ──
    op.add_column(
        "escalation_policies",
        sa.Column("repeat", sa.Boolean, nullable=False, server_default="false"),
    )
    op.execute(
        "UPDATE escalation_policies SET repeat = (repeat_count > 0)"
    )
    op.drop_column("escalation_policies", "repeat_count")

    # ── Revert oncall_schedules ──
    op.drop_column("oncall_schedules", "rotation_interval_hours")

    # Note: Cannot remove an enum value from PostgreSQL; 'hourly' will remain
