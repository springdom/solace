import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from backend.core.notifications import (
    _rate_limit_cache,
    check_rate_limit,
    format_email_html,
    format_slack_message,
    matches_filters,
)
from backend.models import (
    Alert,
    AlertStatus,
    ChannelType,
    Incident,
    IncidentStatus,
    NotificationChannel,
    Severity,
)


def _make_channel(
    channel_type: ChannelType = ChannelType.SLACK,
    filters: dict | None = None,
    is_active: bool = True,
) -> NotificationChannel:
    channel = MagicMock(spec=NotificationChannel)
    channel.id = uuid.uuid4()
    channel.name = "test-channel"
    channel.channel_type = channel_type
    channel.is_active = is_active
    channel.filters = filters or {}
    channel.config = {"webhook_url": "https://hooks.slack.com/test"}
    return channel


def _make_incident(
    severity: Severity = Severity.CRITICAL,
    status: IncidentStatus = IncidentStatus.OPEN,
    alerts: list | None = None,
) -> Incident:
    incident = MagicMock(spec=Incident)
    incident.id = uuid.uuid4()
    incident.title = "Test Incident"
    incident.severity = severity
    incident.status = status
    incident.alerts = alerts or []
    incident.started_at = datetime.now(UTC)
    return incident


def _make_alert(
    service: str = "api",
    severity: Severity = Severity.CRITICAL,
) -> Alert:
    alert = MagicMock(spec=Alert)
    alert.id = uuid.uuid4()
    alert.name = "Test Alert"
    alert.service = service
    alert.severity = severity
    alert.status = AlertStatus.FIRING
    alert.host = "web-01"
    return alert


# ─── Filter Matching Tests ───────────────────────────────


class TestFilterMatching:
    def test_empty_filters_match_all(self):
        channel = _make_channel(filters={})
        incident = _make_incident()
        assert matches_filters(channel, incident) is True

    def test_severity_filter_matches(self):
        channel = _make_channel(filters={"severity": ["critical", "high"]})
        incident = _make_incident(severity=Severity.CRITICAL)
        assert matches_filters(channel, incident) is True

    def test_severity_filter_no_match(self):
        channel = _make_channel(filters={"severity": ["low", "info"]})
        incident = _make_incident(severity=Severity.CRITICAL)
        assert matches_filters(channel, incident) is False

    def test_service_filter_matches(self):
        alert = _make_alert(service="api")
        channel = _make_channel(filters={"service": ["api", "web"]})
        incident = _make_incident(alerts=[alert])
        assert matches_filters(channel, incident) is True

    def test_service_filter_no_match(self):
        alert = _make_alert(service="database")
        channel = _make_channel(filters={"service": ["api", "web"]})
        incident = _make_incident(alerts=[alert])
        assert matches_filters(channel, incident) is False

    def test_combined_filters_both_match(self):
        alert = _make_alert(service="api")
        channel = _make_channel(filters={"severity": ["critical"], "service": ["api"]})
        incident = _make_incident(severity=Severity.CRITICAL, alerts=[alert])
        assert matches_filters(channel, incident) is True

    def test_combined_filters_partial_match_fails(self):
        alert = _make_alert(service="database")
        channel = _make_channel(filters={"severity": ["critical"], "service": ["api"]})
        incident = _make_incident(severity=Severity.CRITICAL, alerts=[alert])
        assert matches_filters(channel, incident) is False

    def test_empty_severity_list_matches_all(self):
        channel = _make_channel(filters={"severity": []})
        incident = _make_incident(severity=Severity.INFO)
        assert matches_filters(channel, incident) is True

    def test_empty_service_list_matches_all(self):
        channel = _make_channel(filters={"service": []})
        incident = _make_incident()
        assert matches_filters(channel, incident) is True


# ─── Rate Limiting Tests ─────────────────────────────────


class TestRateLimiting:
    def setup_method(self):
        _rate_limit_cache.clear()

    def test_first_notification_allowed(self):
        assert check_rate_limit("channel-1", "incident-1") is True

    def test_second_notification_within_cooldown_blocked(self):
        check_rate_limit("channel-1", "incident-1")
        assert check_rate_limit("channel-1", "incident-1") is False

    def test_different_incidents_independent(self):
        check_rate_limit("channel-1", "incident-1")
        assert check_rate_limit("channel-1", "incident-2") is True

    def test_different_channels_independent(self):
        check_rate_limit("channel-1", "incident-1")
        assert check_rate_limit("channel-2", "incident-1") is True

    def test_expired_cooldown_allows_notification(self):
        key = ("channel-1", "incident-1")
        _rate_limit_cache[key] = datetime.now(UTC) - timedelta(seconds=600)
        assert check_rate_limit("channel-1", "incident-1") is True


# ─── Slack Message Formatting ────────────────────────────


class TestSlackFormatting:
    def test_message_contains_incident_title(self):
        incident = _make_incident()
        msg = format_slack_message(incident, "incident_created")
        text = msg["attachments"][0]["blocks"][0]["text"]["text"]
        assert "Test Incident" in text

    def test_message_contains_event_label(self):
        incident = _make_incident()
        msg = format_slack_message(incident, "incident_created")
        text = msg["attachments"][0]["blocks"][0]["text"]["text"]
        assert "New Incident" in text

    def test_message_has_severity_color(self):
        incident = _make_incident(severity=Severity.CRITICAL)
        msg = format_slack_message(incident, "incident_created")
        assert msg["attachments"][0]["color"] == "#ef4444"

    def test_message_has_fields(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        msg = format_slack_message(incident, "incident_created")
        fields = msg["attachments"][0]["blocks"][1]["fields"]
        field_texts = [f["text"] for f in fields]
        assert any("CRITICAL" in t for t in field_texts)
        assert any("1" in t for t in field_texts)  # alert count


# ─── Email Formatting ────────────────────────────────────


class TestEmailFormatting:
    def test_subject_contains_severity_and_title(self):
        incident = _make_incident(severity=Severity.HIGH)
        subject, _ = format_email_html(incident, "incident_created")
        assert "[HIGH]" in subject
        assert "Test Incident" in subject

    def test_subject_contains_event_label(self):
        incident = _make_incident()
        subject, _ = format_email_html(incident, "severity_changed")
        assert "Severity Escalated" in subject

    def test_html_contains_incident_details(self):
        incident = _make_incident()
        _, html = format_email_html(incident, "incident_created")
        assert "Test Incident" in html
        assert "CRITICAL" in html

    def test_html_contains_alert_table(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        _, html = format_email_html(incident, "incident_created")
        assert "Test Alert" in html
        assert "api" in html
