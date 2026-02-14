"""Add on-call schedules, overrides, escalation policies, and mappings.

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2025-02-02 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "h8c9d0e1f2g3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── On-call schedules (sa.Enum will handle creating rotationtype) ──
    op.create_table(
        "oncall_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column(
            "rotation_type",
            sa.Enum("daily", "weekly", "custom", name="rotationtype"),
            nullable=False,
            server_default="weekly",
        ),
        sa.Column("members", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("handoff_time", sa.String(5), nullable=False, server_default="09:00"),
        sa.Column(
            "rotation_interval_days", sa.Integer, nullable=False, server_default="7"
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_oncall_schedules_active", "oncall_schedules", ["is_active"])

    # ── On-call overrides ─────────────────────────────────
    op.create_table(
        "oncall_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "schedule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("oncall_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_oncall_overrides_schedule", "oncall_overrides", ["schedule_id"]
    )
    op.create_index(
        "idx_oncall_overrides_time", "oncall_overrides", ["starts_at", "ends_at"]
    )

    # ── Escalation policies ───────────────────────────────
    op.create_table(
        "escalation_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("repeat", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("levels", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── Service-to-escalation mappings ────────────────────
    op.create_table(
        "service_escalation_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("service_pattern", sa.String(255), nullable=False),
        sa.Column("severity_filter", sa.JSON, nullable=True),
        sa.Column(
            "escalation_policy_id",
            UUID(as_uuid=True),
            sa.ForeignKey("escalation_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_service_escalation_service",
        "service_escalation_mappings",
        ["service_pattern"],
    )


def downgrade() -> None:
    op.drop_table("service_escalation_mappings")
    op.drop_table("escalation_policies")
    op.drop_table("oncall_overrides")
    op.drop_table("oncall_schedules")
    sa.Enum(name="rotationtype").drop(op.get_bind(), checkfirst=True)
