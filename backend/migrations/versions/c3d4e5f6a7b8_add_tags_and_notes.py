"""add tags column and alert_notes table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-12 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add tags column to alerts table
    op.add_column('alerts', sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.create_index('idx_alerts_tags', 'alerts', ['tags'], unique=False, postgresql_using='gin')

    # Create alert_notes table
    op.create_table('alert_notes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('alert_id', sa.UUID(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_alert_notes_alert_id', 'alert_notes', ['alert_id'])
    op.create_index('idx_alert_notes_created_at', 'alert_notes', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_alert_notes_created_at', table_name='alert_notes')
    op.drop_index('idx_alert_notes_alert_id', table_name='alert_notes')
    op.drop_table('alert_notes')

    op.drop_index('idx_alerts_tags', table_name='alerts', postgresql_using='gin')
    op.drop_column('alerts', 'tags')
