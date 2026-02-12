"""add notification_channels and notification_logs tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-12 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enums explicitly (checkfirst=True avoids error if they
    # already exist, e.g. when SQLAlchemy metadata has auto-created them).
    channeltype = postgresql.ENUM(
        'slack', 'email', name='channeltype', create_type=False,
    )
    channeltype.create(op.get_bind(), checkfirst=True)

    notificationstatus = postgresql.ENUM(
        'pending', 'sent', 'failed', name='notificationstatus', create_type=False,
    )
    notificationstatus.create(op.get_bind(), checkfirst=True)

    op.create_table('notification_channels',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column(
            'channel_type',
            postgresql.ENUM('slack', 'email', name='channeltype', create_type=False),
            nullable=False,
        ),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('notification_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('channel_id', sa.UUID(), nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM('pending', 'sent', 'failed', name='notificationstatus', create_type=False),
            nullable=False,
        ),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['notification_channels.id']),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_notification_logs_channel_incident', 'notification_logs', ['channel_id', 'incident_id'])
    op.create_index('idx_notification_logs_created_at', 'notification_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_notification_logs_created_at', table_name='notification_logs')
    op.drop_index('idx_notification_logs_channel_incident', table_name='notification_logs')
    op.drop_table('notification_logs')
    op.drop_table('notification_channels')

    postgresql.ENUM(name='notificationstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='channeltype').drop(op.get_bind(), checkfirst=True)
