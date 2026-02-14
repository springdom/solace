"""Add runbook_rules table for auto-attaching runbook URLs to alerts.

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-02-14 06:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runbook_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_pattern", sa.String(255), nullable=False),
        sa.Column("name_pattern", sa.String(255), nullable=True),
        sa.Column("runbook_url_template", sa.Text(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_runbook_rules_service", "runbook_rules", ["service_pattern"])
    op.create_index("idx_runbook_rules_priority", "runbook_rules", ["priority"])
    op.create_index("idx_runbook_rules_active", "runbook_rules", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_runbook_rules_active", table_name="runbook_rules")
    op.drop_index("idx_runbook_rules_priority", table_name="runbook_rules")
    op.drop_index("idx_runbook_rules_service", table_name="runbook_rules")
    op.drop_table("runbook_rules")
