"""Shared test fixtures for integration tests.

Uses a real PostgreSQL-like setup by mocking at the service boundary.
The conftest provides a configured HTTPX async client pointed at the
FastAPI app, with the DB dependency returning a mock session.

For tests that need actual DB interaction, use a Docker PostgreSQL.
For CI-friendly tests (these), we mock the DB layer and test the
HTTP routing, validation, serialization, and auth layers.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.database import get_db
from backend.models import (
    Alert,
    AlertStatus,
    Incident,
    IncidentStatus,
    Severity,
)


def _make_alert(**overrides) -> Alert:
    """Create a realistic Alert mock."""
    alert = MagicMock(spec=Alert)
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "fingerprint": "abc123def456",
        "source": "generic",
        "source_instance": None,
        "status": AlertStatus.FIRING,
        "severity": Severity.WARNING,
        "name": "TestAlert",
        "description": "Test description",
        "service": "test-svc",
        "environment": None,
        "host": "web-01",
        "labels": {},
        "annotations": {},
        "tags": [],
        "raw_payload": {},
        "starts_at": now,
        "ends_at": None,
        "last_received_at": now,
        "acknowledged_at": None,
        "acknowledged_by": None,
        "resolved_at": None,
        "duplicate_count": 1,
        "generator_url": None,
        "runbook_url": None,
        "ticket_url": None,
        "archived_at": None,
        "incident_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(alert, k, v)

    # Make __table__.columns work for incident routes
    col_keys = [
        "id", "title", "status", "severity", "summary", "started_at",
        "acknowledged_at", "resolved_at", "assigned_to", "created_at", "updated_at",
    ]
    cols = []
    for key in col_keys:
        col = MagicMock()
        col.key = key
        cols.append(col)
    alert.__table__ = MagicMock()
    alert.__table__.columns = cols

    return alert


def _make_incident(**overrides) -> Incident:
    """Create a realistic Incident mock."""
    incident = MagicMock(spec=Incident)
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "title": "test-svc — TestAlert",
        "status": IncidentStatus.OPEN,
        "severity": Severity.WARNING,
        "summary": "Test description",
        "phase": None,
        "started_at": now,
        "acknowledged_at": None,
        "resolved_at": None,
        "assigned_to": None,
        "alerts": [],
        "events": [],
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(incident, k, v)

    # Make __table__.columns work
    col_keys = [
        "id", "title", "status", "severity", "summary", "phase", "started_at",
        "acknowledged_at", "resolved_at", "assigned_to", "created_at", "updated_at",
    ]
    cols = []
    for key in col_keys:
        col = MagicMock()
        col.key = key
        cols.append(col)
    incident.__table__ = MagicMock()
    incident.__table__.columns = cols

    return incident


@pytest.fixture()
def mock_alert():
    return _make_alert


@pytest.fixture()
def mock_incident():
    return _make_incident


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client wired to the FastAPI app with a mock DB session."""
    from backend.main import app

    mock_session = AsyncMock()

    async def _override_db() -> AsyncGenerator:
        yield mock_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
