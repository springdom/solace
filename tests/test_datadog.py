from backend.integrations.datadog import DatadogNormalizer

# ─── Fixtures ────────────────────────────────────────────

BASIC_PAYLOAD = {
    "id": "123456789",
    "title": "[Triggered] CPU is high on web-01",
    "text": "CPU usage is above 95% for the last 10 minutes.",
    "date": 1705305600,
    "alert_id": "12345",
    "alert_type": "error",
    "alert_transition": "Triggered",
    "event_type": "metric_alert_monitor",
    "hostname": "web-01",
    "priority": "P1",
    "tags": "service:api,env:production,team:backend",
    "org": {"id": "12345", "name": "MyOrg"},
    "url": "https://app.datadoghq.com/monitors#123456",
    "link": "https://app.datadoghq.com/event/event?id=123456",
}

RICH_PAYLOAD = {
    "id": "987654321",
    "title": "[Triggered] Disk usage critical on db-01",
    "text": "Disk usage is above 90% on /data volume.",
    "date": 1705305600,
    "alert_id": "67890",
    "alert_type": "error",
    "alert_transition": "Triggered",
    "event_type": "metric_alert_monitor",
    "hostname": "db-01",
    "priority": "P2",
    "tags": "service:database,env:staging,region:us-east-1,disk:/data",
    "org": {"id": "12345", "name": "MyOrg"},
    "url": "https://app.datadoghq.com/monitors#67890",
}

MINIMAL_PAYLOAD = {
    "title": "[Triggered] Something happened",
    "alert_transition": "Triggered",
}

RECOVERED_PAYLOAD = {
    "id": "123456789",
    "title": "[Recovered] CPU is high on web-01",
    "text": "CPU usage has recovered.",
    "date": 1705309200,
    "alert_id": "12345",
    "alert_type": "success",
    "alert_transition": "Recovered",
    "hostname": "web-01",
    "priority": "P1",
    "tags": "service:api,env:production",
    "url": "https://app.datadoghq.com/monitors#123456",
}

NO_TAGS_PAYLOAD = {
    "title": "[Triggered] Alert without tags",
    "alert_transition": "Triggered",
    "alert_type": "warning",
    "hostname": "server-01",
    "tags": "",
}


# ─── Validation Tests ────────────────────────────────────


class TestDatadogValidation:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def test_valid_payload(self):
        assert self.normalizer.validate(BASIC_PAYLOAD) is True

    def test_valid_minimal_payload(self):
        assert self.normalizer.validate(MINIMAL_PAYLOAD) is True

    def test_missing_title(self):
        payload = {"alert_transition": "Triggered", "hostname": "web-01"}
        assert self.normalizer.validate(payload) is False

    def test_missing_both_transition_and_type(self):
        payload = {"title": "Test", "hostname": "web-01"}
        assert self.normalizer.validate(payload) is False

    def test_valid_with_alert_type_only(self):
        """alert_type without alert_transition should still validate."""
        payload = {"title": "Test", "alert_type": "error"}
        assert self.normalizer.validate(payload) is True

    def test_prometheus_payload_rejected(self):
        prometheus = {
            "version": "4",
            "alerts": [{"labels": {"alertname": "Test"}, "status": "firing"}],
        }
        assert self.normalizer.validate(prometheus) is False

    def test_splunk_payload_rejected(self):
        splunk = {"sid": "abc", "result": {"host": "web-01"}, "search_name": "Test"}
        assert self.normalizer.validate(splunk) is False


# ─── Normalization Tests ─────────────────────────────────


class TestDatadogNormalization:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def test_basic_fields(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert len(alerts) == 1

        alert = alerts[0]
        assert alert.name == "CPU is high on web-01"
        assert alert.source == "datadog"
        assert alert.severity == "critical"
        assert alert.status == "firing"

    def test_title_prefix_stripped(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].name == "CPU is high on web-01"
        assert "[Triggered]" not in alerts[0].name

    def test_recovered_prefix_stripped(self):
        alerts = self.normalizer.normalize(RECOVERED_PAYLOAD)
        assert alerts[0].name == "CPU is high on web-01"
        assert "[Recovered]" not in alerts[0].name

    def test_hostname_extracted(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].host == "web-01"

    def test_service_from_tags(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].service == "api"

    def test_environment_from_tags(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].environment == "production"

    def test_description(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].description == "CPU usage is above 95% for the last 10 minutes."

    def test_generator_url(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].generator_url == "https://app.datadoghq.com/monitors#123456"

    def test_starts_at_from_epoch(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].starts_at is not None
        assert alerts[0].starts_at.year == 2024

    def test_raw_payload_preserved(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].raw_payload is not None
        assert alerts[0].raw_payload["alert_id"] == "12345"

    def test_tags_parsed_into_labels(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        labels = alerts[0].labels
        assert labels["team"] == "backend"
        # service and env should be extracted, not in labels
        assert "service" not in labels
        assert "env" not in labels

    def test_datadog_metadata_in_labels(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        labels = alerts[0].labels
        assert labels["datadog_alert_id"] == "12345"
        assert labels["datadog_event_type"] == "metric_alert_monitor"
        assert labels["datadog_org"] == "MyOrg"

    def test_event_link_in_annotations(self):
        alerts = self.normalizer.normalize(BASIC_PAYLOAD)
        assert alerts[0].annotations["event_link"] == "https://app.datadoghq.com/event/event?id=123456"

    def test_minimal_payload_defaults(self):
        alerts = self.normalizer.normalize(MINIMAL_PAYLOAD)
        alert = alerts[0]
        assert alert.name == "Something happened"
        assert alert.source == "datadog"
        assert alert.status == "firing"
        assert alert.host is None
        assert alert.service is None

    def test_empty_tags(self):
        alerts = self.normalizer.normalize(NO_TAGS_PAYLOAD)
        assert alerts[0].service is None
        assert alerts[0].environment is None


# ─── Resolved Status Tests ───────────────────────────────


class TestDatadogResolved:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def test_recovered_maps_to_resolved(self):
        alerts = self.normalizer.normalize(RECOVERED_PAYLOAD)
        assert alerts[0].status == "resolved"

    def test_recovered_severity_from_priority(self):
        """Even recovered alerts should retain their priority-based severity."""
        alerts = self.normalizer.normalize(RECOVERED_PAYLOAD)
        assert alerts[0].severity == "critical"


# ─── Priority & Severity Mapping Tests ───────────────────


class TestDatadogSeverityMapping:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def _make_payload(self, priority: str | None = None, alert_type: str | None = None):
        payload = {
            "title": "[Triggered] Test",
            "alert_transition": "Triggered",
        }
        if priority:
            payload["priority"] = priority
        if alert_type:
            payload["alert_type"] = alert_type
        return payload

    def test_p1_is_critical(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P1"))
        assert alerts[0].severity == "critical"

    def test_p2_is_high(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P2"))
        assert alerts[0].severity == "high"

    def test_p3_is_warning(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P3"))
        assert alerts[0].severity == "warning"

    def test_p4_is_low(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P4"))
        assert alerts[0].severity == "low"

    def test_p5_is_info(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P5"))
        assert alerts[0].severity == "info"

    def test_alert_type_error_is_critical(self):
        alerts = self.normalizer.normalize(self._make_payload(alert_type="error"))
        assert alerts[0].severity == "critical"

    def test_alert_type_warning(self):
        alerts = self.normalizer.normalize(self._make_payload(alert_type="warning"))
        assert alerts[0].severity == "warning"

    def test_alert_type_info(self):
        alerts = self.normalizer.normalize(self._make_payload(alert_type="info"))
        assert alerts[0].severity == "info"

    def test_priority_takes_precedence_over_alert_type(self):
        alerts = self.normalizer.normalize(self._make_payload(priority="P4", alert_type="error"))
        assert alerts[0].severity == "low"  # P4 wins over error

    def test_no_priority_no_type_defaults_to_warning(self):
        alerts = self.normalizer.normalize(self._make_payload())
        assert alerts[0].severity == "warning"


# ─── Tag Parsing Tests ───────────────────────────────────


class TestDatadogTagParsing:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def test_simple_tags(self):
        payload = {
            "title": "Test",
            "alert_transition": "Triggered",
            "tags": "service:web,env:prod,team:ops",
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].service == "web"
        assert alerts[0].environment == "prod"
        assert alerts[0].labels["team"] == "ops"

    def test_tags_with_valueless_entries(self):
        payload = {
            "title": "Test",
            "alert_transition": "Triggered",
            "tags": "service:api,critical,env:staging",
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].service == "api"
        assert alerts[0].labels["critical"] == ""

    def test_tags_with_whitespace(self):
        payload = {
            "title": "Test",
            "alert_transition": "Triggered",
            "tags": " service:api , env:prod , team:backend ",
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].service == "api"
        assert alerts[0].environment == "prod"


# ─── Status Transition Tests ─────────────────────────────


class TestDatadogStatusMapping:
    def setup_method(self):
        self.normalizer = DatadogNormalizer()

    def _make_payload(self, transition: str):
        return {
            "title": f"[{transition}] Test",
            "alert_transition": transition,
        }

    def test_triggered_is_firing(self):
        alerts = self.normalizer.normalize(self._make_payload("Triggered"))
        assert alerts[0].status == "firing"

    def test_re_triggered_is_firing(self):
        alerts = self.normalizer.normalize(self._make_payload("Re-Triggered"))
        assert alerts[0].status == "firing"

    def test_recovered_is_resolved(self):
        alerts = self.normalizer.normalize(self._make_payload("Recovered"))
        assert alerts[0].status == "resolved"

    def test_no_data_is_firing(self):
        alerts = self.normalizer.normalize(self._make_payload("No Data"))
        assert alerts[0].status == "firing"

    def test_unknown_transition_defaults_to_firing(self):
        alerts = self.normalizer.normalize(self._make_payload("SomethingNew"))
        assert alerts[0].status == "firing"
