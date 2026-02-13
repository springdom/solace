"""Add teams, webhook, pagerduty notification channel types.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: convert column to text, drop old enum, recreate with new values, cast back
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE text")
    op.execute("DROP TYPE channeltype")
    op.execute(
        "CREATE TYPE channeltype AS ENUM "
        "('slack', 'email', 'teams', 'webhook', 'pagerduty')"
    )
    op.execute(
        "ALTER TABLE notification_channels "
        "ALTER COLUMN channel_type TYPE channeltype USING channel_type::channeltype"
    )


def downgrade() -> None:
    # Remove new values by converting back
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE text")
    op.execute("DROP TYPE channeltype")
    op.execute("CREATE TYPE channeltype AS ENUM ('slack', 'email')")
    op.execute(
        "ALTER TABLE notification_channels "
        "ALTER COLUMN channel_type TYPE channeltype USING channel_type::channeltype"
    )
