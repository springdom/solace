"""Integration tests for the API layer.

Tests HTTP routing, request validation, response serialization,
and auth by mocking at the service/DB boundary. This avoids needing
a real PostgreSQL instance while still exercising the full FastAPI
request pipeline.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from backend.models import (
    Alert,
    AlertNote,
    AlertStatus,
    Incident,
    IncidentEvent,
    IncidentStatus,
    Severity,
)

# ── Helpers ──────────────────────────────────────────────────


def _alert(**kw) -> MagicMock:
    """Build a mock Alert with realistic defaults."""
    now = datetime.now(UTC)
    alert = MagicMock(spec=Alert)
    defaults = dict(
        id=uuid.uuid4(), fingerprint="abc123", source="generic",
        source_instance=None, status=AlertStatus.FIRING,
        severity=Severity.WARNING, name="TestAlert",
        description="desc", service="test-svc", environment=None,
        host="web-01", labels={}, annotations={}, tags=[],
        raw_payload={}, starts_at=now, ends_at=None,
        last_received_at=now, acknowledged_at=None,
        acknowledged_by=None, resolved_at=None, duplicate_count=1,
        generator_url=None, incident_id=None,
        created_at=now, updated_at=now,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(alert, k, v)
    return alert


def _incident(**kw) -> MagicMock:
    """Build a mock Incident with realistic defaults."""
    now = datetime.now(UTC)
    inc = MagicMock(spec=Incident)
    defaults = dict(
        id=uuid.uuid4(), title="test-svc — TestAlert",
        status=IncidentStatus.OPEN, severity=Severity.WARNING,
        summary="desc", started_at=now, acknowledged_at=None,
        resolved_at=None, assigned_to=None, alerts=[], events=[],
        created_at=now, updated_at=now,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(inc, k, v)

    # __table__.columns used by _incident_to_response
    cols = []
    for key in ["id", "title", "status", "severity", "summary",
                "started_at", "acknowledged_at", "resolved_at",
                "assigned_to", "created_at", "updated_at"]:
        c = MagicMock()
        c.key = key
        cols.append(c)
    inc.__table__ = MagicMock()
    inc.__table__.columns = cols
    return inc


def _note(**kw) -> MagicMock:
    now = datetime.now(UTC)
    note = MagicMock(spec=AlertNote)
    defaults = dict(
        id=uuid.uuid4(), alert_id=uuid.uuid4(),
        text="Note text", author="alice",
        created_at=now, updated_at=now,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(note, k, v)
    return note


def _event(**kw) -> MagicMock:
    now = datetime.now(UTC)
    ev = MagicMock(spec=IncidentEvent)
    defaults = dict(
        id=uuid.uuid4(), event_type="incident_created",
        description="created", actor="system",
        event_data={}, created_at=now,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(ev, k, v)
    return ev


# ─── Health ────────────────────────────────────────────────────


class TestHealth:
    async def test_liveness(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_readiness_returns_status(self, client: AsyncClient):
        r = await client.get("/health/ready")
        assert r.status_code in (200, 503)
        body = r.json()
        assert "status" in body
        assert "checks" in body


# ─── Webhook Ingestion ─────────────────────────────────────────


class TestWebhookIngestion:
    @patch("backend.api.routes.webhooks.ingest_alert", new_callable=AsyncMock)
    async def test_valid_generic_webhook(self, mock_ingest, client: AsyncClient):
        a = _alert(incident_id=uuid.uuid4())
        mock_ingest.return_value = (a, False)

        r = await client.post("/api/v1/webhooks/generic", json={
            "name": "HighCPU", "severity": "critical", "service": "api",
        })
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert body["is_duplicate"] is False
        mock_ingest.assert_called_once()

    @patch("backend.api.routes.webhooks.ingest_alert", new_callable=AsyncMock)
    async def test_duplicate_webhook(self, mock_ingest, client: AsyncClient):
        a = _alert(duplicate_count=3)
        mock_ingest.return_value = (a, True)

        r = await client.post("/api/v1/webhooks/generic", json={
            "name": "HighCPU", "severity": "critical", "service": "api",
        })
        assert r.status_code == 202
        assert r.json()["is_duplicate"] is True
        assert r.json()["duplicate_count"] == 3

    async def test_unknown_provider_returns_400(self, client: AsyncClient):
        r = await client.post("/api/v1/webhooks/nonexistent", json={"name": "x"})
        assert r.status_code == 400
        assert "Unknown provider" in r.json()["detail"]

    async def test_invalid_json_returns_400(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/webhooks/generic",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400

    async def test_missing_required_fields_returns_422(self, client: AsyncClient):
        r = await client.post("/api/v1/webhooks/generic", json={"nope": "bad"})
        assert r.status_code == 422


# ─── Alert CRUD ────────────────────────────────────────────────


class TestAlertCrud:
    @patch("backend.api.routes.alerts.get_alerts", new_callable=AsyncMock)
    async def test_list_alerts(self, mock_get, client: AsyncClient):
        a1, a2 = _alert(name="A1"), _alert(name="A2")
        mock_get.return_value = ([a1, a2], 2)

        r = await client.get("/api/v1/alerts")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["alerts"]) == 2

    @patch("backend.api.routes.alerts.get_alerts", new_callable=AsyncMock)
    async def test_list_alerts_with_filters(self, mock_get, client: AsyncClient):
        mock_get.return_value = ([], 0)

        r = await client.get(
            "/api/v1/alerts?status=firing&severity=critical&q=cpu&page=2&page_size=10"
        )
        assert r.status_code == 200
        mock_get.assert_called_once()
        call_kw = mock_get.call_args
        # Verify filters are passed through
        assert call_kw.kwargs.get("status") == "firing" or call_kw[1].get("status") == "firing"

    async def test_get_alert_by_id(self, client: AsyncClient):
        a = _alert()
        from backend.database import get_db
        from backend.main import app

        mock_db = AsyncMock()
        # db.execute() returns a result whose .scalar_one_or_none() is sync
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = a
        mock_db.execute.return_value = mock_result

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        r = await client.get(f"/api/v1/alerts/{a.id}")
        app.dependency_overrides.pop(get_db, None)

        assert r.status_code == 200
        assert r.json()["name"] == "TestAlert"

    async def test_get_nonexistent_alert_returns_404(self, client: AsyncClient):
        from backend.database import get_db
        from backend.main import app

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        r = await client.get(f"/api/v1/alerts/{uuid.uuid4()}")
        app.dependency_overrides.pop(get_db, None)
        assert r.status_code == 404

    @patch("backend.api.routes.alerts.acknowledge_alert", new_callable=AsyncMock)
    async def test_acknowledge_alert(self, mock_ack, client: AsyncClient):
        a = _alert(status=AlertStatus.ACKNOWLEDGED, acknowledged_at=datetime.now(UTC))
        mock_ack.return_value = a

        r = await client.post(f"/api/v1/alerts/{a.id}/acknowledge")
        assert r.status_code == 200
        assert r.json()["status"] == "acknowledged"

    @patch("backend.api.routes.alerts.resolve_alert", new_callable=AsyncMock)
    async def test_resolve_alert(self, mock_resolve, client: AsyncClient):
        a = _alert(status=AlertStatus.RESOLVED, resolved_at=datetime.now(UTC))
        mock_resolve.return_value = a

        r = await client.post(f"/api/v1/alerts/{a.id}/resolve")
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"

    @patch("backend.api.routes.alerts.acknowledge_alert", new_callable=AsyncMock)
    async def test_acknowledge_nonexistent_returns_404(self, mock_ack, client):
        mock_ack.return_value = None

        r = await client.post(
            f"/api/v1/alerts/{uuid.uuid4()}/acknowledge"
        )
        assert r.status_code == 404


# ─── Tags ──────────────────────────────────────────────────────


class TestAlertTags:
    @patch("backend.api.routes.alerts.add_alert_tag", new_callable=AsyncMock)
    async def test_add_tag(self, mock_add, client: AsyncClient):
        a = _alert(tags=["urgent"])
        mock_add.return_value = a

        r = await client.post(f"/api/v1/alerts/{a.id}/tags/urgent")
        assert r.status_code == 200
        assert "urgent" in r.json()["tags"]

    @patch("backend.api.routes.alerts.remove_alert_tag", new_callable=AsyncMock)
    async def test_remove_tag(self, mock_remove, client: AsyncClient):
        a = _alert(tags=[])
        mock_remove.return_value = a

        r = await client.delete(f"/api/v1/alerts/{a.id}/tags/old")
        assert r.status_code == 200

    @patch("backend.api.routes.alerts.update_alert_tags", new_callable=AsyncMock)
    async def test_set_tags(self, mock_set, client: AsyncClient):
        a = _alert(tags=["a", "b", "c"])
        mock_set.return_value = a

        r = await client.put(
            f"/api/v1/alerts/{a.id}/tags",
            json={"tags": ["a", "b", "c"]},
        )
        assert r.status_code == 200
        assert sorted(r.json()["tags"]) == ["a", "b", "c"]


# ─── Notes ─────────────────────────────────────────────────────


class TestAlertNotes:
    @patch("backend.api.routes.alerts.create_alert_note", new_callable=AsyncMock)
    async def test_add_note(self, mock_create, client: AsyncClient):
        alert_id = uuid.uuid4()
        note = _note(alert_id=alert_id, text="Investigating", author="alice")
        mock_create.return_value = note

        r = await client.post(
            f"/api/v1/alerts/{alert_id}/notes",
            json={"text": "Investigating", "author": "alice"},
        )
        assert r.status_code == 201
        assert r.json()["text"] == "Investigating"

    @patch("backend.api.routes.alerts.get_alert_notes", new_callable=AsyncMock)
    async def test_list_notes(self, mock_list, client: AsyncClient):
        alert_id = uuid.uuid4()
        mock_list.return_value = [_note(), _note()]

        r = await client.get(f"/api/v1/alerts/{alert_id}/notes")
        assert r.status_code == 200
        assert r.json()["total"] == 2

    @patch("backend.api.routes.alerts.update_alert_note", new_callable=AsyncMock)
    async def test_update_note(self, mock_update, client: AsyncClient):
        note = _note(text="Updated")
        mock_update.return_value = note

        r = await client.put(
            f"/api/v1/alerts/notes/{note.id}",
            json={"text": "Updated"},
        )
        assert r.status_code == 200
        assert r.json()["text"] == "Updated"

    @patch("backend.api.routes.alerts.delete_alert_note", new_callable=AsyncMock)
    async def test_delete_note(self, mock_delete, client: AsyncClient):
        mock_delete.return_value = True

        r = await client.delete(f"/api/v1/alerts/notes/{uuid.uuid4()}")
        assert r.status_code == 204


# ─── Incidents ─────────────────────────────────────────────────


class TestIncidents:
    @patch("backend.api.routes.incidents.get_incidents", new_callable=AsyncMock)
    async def test_list_incidents(self, mock_get, client: AsyncClient):
        inc = _incident()
        mock_get.return_value = ([inc], 1)

        r = await client.get("/api/v1/incidents")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    @patch("backend.api.routes.incidents.get_incident", new_callable=AsyncMock)
    async def test_get_incident_detail(self, mock_get, client: AsyncClient):
        ev = _event()
        inc = _incident(events=[ev], alerts=[_alert()])
        mock_get.return_value = inc

        r = await client.get(f"/api/v1/incidents/{inc.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(inc.id)
        assert len(body["events"]) == 1
        assert len(body["alerts"]) == 1

    @patch("backend.api.routes.incidents.get_incident", new_callable=AsyncMock)
    async def test_get_nonexistent_incident_returns_404(self, mock_get, client):
        mock_get.return_value = None

        r = await client.get(f"/api/v1/incidents/{uuid.uuid4()}")
        assert r.status_code == 404

    @patch("backend.api.routes.incidents.acknowledge_incident", new_callable=AsyncMock)
    async def test_acknowledge_incident(self, mock_ack, client: AsyncClient):
        inc = _incident(status=IncidentStatus.ACKNOWLEDGED)
        mock_ack.return_value = inc

        r = await client.post(f"/api/v1/incidents/{inc.id}/acknowledge")
        assert r.status_code == 200
        assert r.json()["status"] == "acknowledged"

    @patch("backend.api.routes.incidents.resolve_incident", new_callable=AsyncMock)
    async def test_resolve_incident(self, mock_resolve, client: AsyncClient):
        inc = _incident(status=IncidentStatus.RESOLVED, resolved_at=datetime.now(UTC))
        mock_resolve.return_value = inc

        r = await client.post(f"/api/v1/incidents/{inc.id}/resolve")
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"


# ─── Stats ─────────────────────────────────────────────────────


class TestStats:
    @patch("backend.api.routes.stats.get_stats", new_callable=AsyncMock)
    async def test_stats_endpoint(self, mock_stats, client: AsyncClient):
        mock_stats.return_value = {
            "alerts": {
                "by_status": {"firing": 5, "acknowledged": 2, "resolved": 10},
                "by_severity": {"critical": 1, "high": 3, "warning": 3},
                "total": 17,
                "active": 7,
            },
            "incidents": {
                "by_status": {"open": 2, "acknowledged": 1, "resolved": 5},
                "total": 8,
            },
            "mtta_seconds": 120.5,
            "mttr_seconds": 3600.0,
        }

        r = await client.get("/api/v1/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["alerts"]["total"] == 17
        assert body["incidents"]["total"] == 8
        assert body["mtta_seconds"] == 120.5


# ─── Auth ──────────────────────────────────────────────────────


class TestApiAuth:
    async def test_health_requires_no_auth(self, client: AsyncClient):
        """Health endpoints should never require auth."""
        r = await client.get("/health")
        assert r.status_code == 200

    @patch("backend.api.routes.alerts.get_alerts", new_callable=AsyncMock)
    async def test_api_accessible_in_dev_mode(self, mock_get, client: AsyncClient):
        """In dev mode with empty API_KEY, requests should pass through."""
        mock_get.return_value = ([], 0)
        r = await client.get("/api/v1/alerts")
        # Should work because APP_ENV=development and API_KEY is empty
        assert r.status_code == 200

    @patch("backend.config.get_settings")
    @patch("backend.api.routes.alerts.get_alerts", new_callable=AsyncMock)
    async def test_api_rejects_missing_key_in_production(
        self, mock_get, mock_settings, client: AsyncClient
    ):
        """When API_KEY is set, requests without key should be rejected."""
        # This is tricky to test with the singleton settings, so we just
        # verify the dep function directly
        from fastapi import HTTPException

        # Save original
        from backend.api import deps
        from backend.api.deps import require_api_key
        orig_settings = deps.settings

        try:
            mock_s = MagicMock()
            mock_s.is_dev = False
            mock_s.api_key = "real-secret-key"
            deps.settings = mock_s

            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key=None)
            assert exc_info.value.status_code == 401

            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="wrong-key")
            assert exc_info.value.status_code == 403

            # Valid key should pass
            result = await require_api_key(api_key="real-secret-key")
            assert result == "real-secret-key"
        finally:
            deps.settings = orig_settings


# ─── Silences ──────────────────────────────────────────────────


class TestSilences:
    async def test_create_silence_validation(self, client: AsyncClient):
        """ends_at must be after starts_at."""
        r = await client.post("/api/v1/silences", json={
            "name": "test",
            "matchers": {},
            "starts_at": "2026-01-02T00:00:00Z",
            "ends_at": "2026-01-01T00:00:00Z",
        })
        assert r.status_code == 400


# ─── Notifications ─────────────────────────────────────────────


class TestNotificationChannels:
    async def test_create_slack_without_webhook_url(self, client: AsyncClient):
        """Slack channels must have webhook_url in config."""
        r = await client.post("/api/v1/notifications/channels", json={
            "name": "bad-slack",
            "channel_type": "slack",
            "config": {},
        })
        assert r.status_code == 400
        assert "webhook_url" in r.json()["detail"]

    async def test_create_email_without_recipients(self, client: AsyncClient):
        """Email channels must have recipients in config."""
        r = await client.post("/api/v1/notifications/channels", json={
            "name": "bad-email",
            "channel_type": "email",
            "config": {},
        })
        assert r.status_code == 400
        assert "recipients" in r.json()["detail"]

    async def test_create_invalid_channel_type(self, client: AsyncClient):
        r = await client.post("/api/v1/notifications/channels", json={
            "name": "bad",
            "channel_type": "telegram",
            "config": {},
        })
        assert r.status_code == 400
        assert "Invalid channel_type" in r.json()["detail"]
