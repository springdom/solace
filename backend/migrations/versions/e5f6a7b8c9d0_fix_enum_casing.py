"""fix enum casing: uppercase to lowercase values

PostgreSQL enum values were created as UPPERCASE (FIRING, CRITICAL, etc.)
but SQLAlchemy with values_callable expects lowercase (firing, critical, etc.).

Strategy: Drop enum constraints, convert columns to text, update values to
lowercase, recreate enum types with only lowercase values, cast back.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-13 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── alertstatus enum ──────────────────────────────────
    # Convert column to text, update values, recreate enum, cast back
    op.execute("ALTER TABLE alerts ALTER COLUMN status TYPE text")
    op.execute("UPDATE alerts SET status = LOWER(status)")
    op.execute("DROP TYPE alertstatus")
    op.execute("CREATE TYPE alertstatus AS ENUM ('firing', 'acknowledged', 'resolved', 'suppressed', 'archived')")
    op.execute("ALTER TABLE alerts ALTER COLUMN status TYPE alertstatus USING status::alertstatus")

    # ── severity enum ─────────────────────────────────────
    # Used by both alerts and incidents tables
    op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE text")
    op.execute("ALTER TABLE incidents ALTER COLUMN severity TYPE text")
    op.execute("UPDATE alerts SET severity = LOWER(severity)")
    op.execute("UPDATE incidents SET severity = LOWER(severity)")
    op.execute("DROP TYPE severity")
    op.execute("CREATE TYPE severity AS ENUM ('critical', 'high', 'warning', 'low', 'info')")
    op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE severity USING severity::severity")
    op.execute("ALTER TABLE incidents ALTER COLUMN severity TYPE severity USING severity::severity")

    # ── incidentstatus enum ───────────────────────────────
    op.execute("ALTER TABLE incidents ALTER COLUMN status TYPE text")
    op.execute("UPDATE incidents SET status = LOWER(status)")
    op.execute("DROP TYPE incidentstatus")
    op.execute("CREATE TYPE incidentstatus AS ENUM ('open', 'acknowledged', 'resolved')")
    op.execute("ALTER TABLE incidents ALTER COLUMN status TYPE incidentstatus USING status::incidentstatus")

    # ── channeltype enum ──────────────────────────────────
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE text")
    op.execute("UPDATE notification_channels SET channel_type = LOWER(channel_type)")
    op.execute("DROP TYPE channeltype")
    op.execute("CREATE TYPE channeltype AS ENUM ('slack', 'email')")
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE channeltype USING channel_type::channeltype")

    # ── notificationstatus enum ───────────────────────────
    op.execute("ALTER TABLE notification_logs ALTER COLUMN status TYPE text")
    op.execute("UPDATE notification_logs SET status = LOWER(status)")
    op.execute("DROP TYPE notificationstatus")
    op.execute("CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'failed')")
    op.execute("ALTER TABLE notification_logs ALTER COLUMN status TYPE notificationstatus USING status::notificationstatus")


def downgrade() -> None:
    # Reverse: recreate with uppercase values

    # ── alertstatus ───────────────────────────────────────
    op.execute("ALTER TABLE alerts ALTER COLUMN status TYPE text")
    op.execute("UPDATE alerts SET status = UPPER(status)")
    op.execute("DROP TYPE alertstatus")
    op.execute("CREATE TYPE alertstatus AS ENUM ('FIRING', 'ACKNOWLEDGED', 'RESOLVED', 'SUPPRESSED', 'ARCHIVED')")
    op.execute("ALTER TABLE alerts ALTER COLUMN status TYPE alertstatus USING status::alertstatus")

    # ── severity ──────────────────────────────────────────
    op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE text")
    op.execute("ALTER TABLE incidents ALTER COLUMN severity TYPE text")
    op.execute("UPDATE alerts SET severity = UPPER(severity)")
    op.execute("UPDATE incidents SET severity = UPPER(severity)")
    op.execute("DROP TYPE severity")
    op.execute("CREATE TYPE severity AS ENUM ('CRITICAL', 'HIGH', 'WARNING', 'LOW', 'INFO')")
    op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE severity USING severity::severity")
    op.execute("ALTER TABLE incidents ALTER COLUMN severity TYPE severity USING severity::severity")

    # ── incidentstatus ────────────────────────────────────
    op.execute("ALTER TABLE incidents ALTER COLUMN status TYPE text")
    op.execute("UPDATE incidents SET status = UPPER(status)")
    op.execute("DROP TYPE incidentstatus")
    op.execute("CREATE TYPE incidentstatus AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')")
    op.execute("ALTER TABLE incidents ALTER COLUMN status TYPE incidentstatus USING status::incidentstatus")

    # ── channeltype ───────────────────────────────────────
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE text")
    op.execute("UPDATE notification_channels SET channel_type = UPPER(channel_type)")
    op.execute("DROP TYPE channeltype")
    op.execute("CREATE TYPE channeltype AS ENUM ('SLACK', 'EMAIL')")
    op.execute("ALTER TABLE notification_channels ALTER COLUMN channel_type TYPE channeltype USING channel_type::channeltype")

    # ── notificationstatus ────────────────────────────────
    op.execute("ALTER TABLE notification_logs ALTER COLUMN status TYPE text")
    op.execute("UPDATE notification_logs SET status = UPPER(status)")
    op.execute("DROP TYPE notificationstatus")
    op.execute("CREATE TYPE notificationstatus AS ENUM ('PENDING', 'SENT', 'FAILED')")
    op.execute("ALTER TABLE notification_logs ALTER COLUMN status TYPE notificationstatus USING status::notificationstatus")
