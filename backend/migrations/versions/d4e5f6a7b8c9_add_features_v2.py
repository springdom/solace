"""add runbook_url, ticket_url, archived_at, alert_occurrences, incident phase

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-13 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add 'archived' value to the alertstatus enum
    op.execute("ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'archived'")

    # Add new columns to alerts table
    op.add_column('alerts', sa.Column('runbook_url', sa.Text(), nullable=True))
    op.add_column('alerts', sa.Column('ticket_url', sa.Text(), nullable=True))
    op.add_column('alerts', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))

    # Add phase column to incidents table
    op.add_column('incidents', sa.Column('phase', sa.String(length=50), nullable=True))

    # Create alert_occurrences table
    op.create_table('alert_occurrences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('alert_id', sa.UUID(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_alert_occurrences_alert_id', 'alert_occurrences', ['alert_id'])
    op.create_index('idx_alert_occurrences_received_at', 'alert_occurrences', ['received_at'])


def downgrade() -> None:
    op.drop_index('idx_alert_occurrences_received_at', table_name='alert_occurrences')
    op.drop_index('idx_alert_occurrences_alert_id', table_name='alert_occurrences')
    op.drop_table('alert_occurrences')

    op.drop_column('incidents', 'phase')
    op.drop_column('alerts', 'archived_at')
    op.drop_column('alerts', 'ticket_url')
    op.drop_column('alerts', 'runbook_url')

    # Note: PostgreSQL does not support removing enum values.
    # The 'archived' value will remain in the enum type after downgrade.
