import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from backend.core.notifications import (
    _rate_limit_cache,
    check_rate_limit,
    format_email_html,
    format_pagerduty_event,
    format_slack_message,
    format_teams_message,
    format_webhook_payload,
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


# ─── Teams Message Formatting ──────────────────────────


class TestTeamsFormatting:
    def test_message_is_adaptive_card(self):
        incident = _make_incident()
        msg = format_teams_message(incident, "incident_created")
        assert msg["type"] == "message"
        card = msg["attachments"][0]["content"]
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.4"

    def test_message_contains_incident_title(self):
        incident = _make_incident()
        msg = format_teams_message(incident, "incident_created")
        body = msg["attachments"][0]["content"]["body"]
        title_block = body[1]["items"][0]
        assert "Test Incident" in title_block["text"]

    def test_message_contains_event_label(self):
        incident = _make_incident()
        msg = format_teams_message(incident, "incident_created")
        body = msg["attachments"][0]["content"]["body"]
        header = body[0]["items"][0]["text"]
        assert "New Incident" in header

    def test_message_has_facts(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        msg = format_teams_message(incident, "incident_created")
        facts = msg["attachments"][0]["content"]["body"][1]["items"][1]["facts"]
        fact_titles = [f["title"] for f in facts]
        assert "Severity" in fact_titles
        assert "Status" in fact_titles
        assert "Alerts" in fact_titles
        assert "Service" in fact_titles

    def test_message_has_action_button(self):
        incident = _make_incident()
        msg = format_teams_message(incident, "incident_created")
        actions = msg["attachments"][0]["content"]["actions"]
        assert len(actions) == 1
        assert actions[0]["type"] == "Action.OpenUrl"
        assert actions[0]["title"] == "View in Solace"


# ─── Webhook Payload Formatting ─────────────────────────


class TestWebhookFormatting:
    def test_payload_has_required_fields(self):
        incident = _make_incident()
        payload = format_webhook_payload(incident, "incident_created")
        assert payload["event_type"] == "incident_created"
        assert payload["source"] == "solace"
        assert "incident" in payload
        assert "timestamp" in payload

    def test_payload_incident_fields(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        payload = format_webhook_payload(incident, "incident_created")
        inc = payload["incident"]
        assert inc["title"] == "Test Incident"
        assert inc["severity"] == "critical"
        assert inc["status"] == "open"
        assert inc["alert_count"] == 1
        assert "api" in inc["services"]

    def test_payload_includes_alert_details(self):
        alert = _make_alert(service="api")
        alert.description = "High CPU"
        alert.duplicate_count = 3
        alert.starts_at = datetime.now(UTC)
        incident = _make_incident(alerts=[alert])
        payload = format_webhook_payload(incident, "incident_created")
        alerts = payload["incident"]["alerts"]
        assert len(alerts) == 1
        assert alerts[0]["name"] == "Test Alert"
        assert alerts[0]["service"] == "api"

    def test_resolved_event(self):
        incident = _make_incident(status=IncidentStatus.RESOLVED)
        incident.resolved_at = datetime.now(UTC)
        payload = format_webhook_payload(incident, "incident_resolved")
        assert payload["event_type"] == "incident_resolved"


# ─── PagerDuty Event Formatting ─────────────────────────


class TestPagerDutyFormatting:
    def test_trigger_event(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        event = format_pagerduty_event(incident, "incident_created", "test-key")
        assert event["routing_key"] == "test-key"
        assert event["event_action"] == "trigger"
        assert f"solace-incident-{incident.id}" == event["dedup_key"]
        assert "payload" in event
        assert event["payload"]["severity"] == "critical"

    def test_resolve_event(self):
        incident = _make_incident()
        event = format_pagerduty_event(incident, "incident_resolved", "test-key")
        assert event["event_action"] == "resolve"
        assert "payload" not in event  # resolve events don't need payload

    def test_severity_mapping(self):
        for solace_sev, pd_sev in [
            (Severity.CRITICAL, "critical"),
            (Severity.HIGH, "error"),
            (Severity.WARNING, "warning"),
            (Severity.LOW, "info"),
            (Severity.INFO, "info"),
        ]:
            incident = _make_incident(severity=solace_sev)
            event = format_pagerduty_event(
                incident, "incident_created", "test-key"
            )
            assert event["payload"]["severity"] == pd_sev

    def test_trigger_has_links(self):
        incident = _make_incident()
        event = format_pagerduty_event(incident, "incident_created", "test-key")
        assert "links" in event
        assert len(event["links"]) == 1
        assert "View in Solace" in event["links"][0]["text"]

    def test_trigger_has_custom_details(self):
        alert = _make_alert(service="api")
        incident = _make_incident(alerts=[alert])
        event = format_pagerduty_event(incident, "incident_created", "test-key")
        details = event["payload"]["custom_details"]
        assert details["alert_count"] == 1
        assert "api" in details["services"]
