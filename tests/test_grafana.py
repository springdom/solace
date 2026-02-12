from backend.integrations.grafana import GrafanaNormalizer

# ─── Fixtures ────────────────────────────────────────────

FULL_PAYLOAD = {
    "receiver": "solace",
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighCPU",
                "instance": "web-01:9090",
                "job": "node",
                "severity": "critical",
                "env": "production",
                "grafana_folder": "Infrastructure",
            },
            "annotations": {
                "summary": "High CPU usage on web-01",
                "description": "CPU usage is above 95% for 10 minutes",
                "runbook_url": "https://runbooks.example.com/cpu",
            },
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://grafana:3000/alerting/grafana/abc123/view",
            "fingerprint": "abc123def456",
            "dashboardURL": "http://grafana:3000/d/abc123/infrastructure",
            "panelURL": "http://grafana:3000/d/abc123/infrastructure?viewPanel=1",
            "silenceURL": "http://grafana:3000/alerting/silence/new?alertmanager=grafana",
            "valueString": "[ var='A' labels={instance=web-01} value=95.3 ]",
        }
    ],
    "groupLabels": {"alertname": "HighCPU"},
    "commonLabels": {"alertname": "HighCPU", "severity": "critical"},
    "commonAnnotations": {"summary": "CPU is high"},
    "externalURL": "http://grafana:3000/",
    "version": "1",
    "groupKey": '{}:{alertname="HighCPU"}',
    "truncatedAlerts": 0,
    "title": "[FIRING:1] HighCPU",
    "state": "alerting",
    "message": "CPU is high",
}

BATCH_PAYLOAD = {
    "status": "firing",
    "title": "[FIRING:2] HighCPU",
    "state": "alerting",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "HighCPU", "instance": "web-01:9090", "severity": "critical"},
            "annotations": {"summary": "CPU high on web-01"},
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "dashboardURL": "http://grafana:3000/d/abc123/infra",
        },
        {
            "status": "firing",
            "labels": {"alertname": "HighCPU", "instance": "web-02:9090", "severity": "warning"},
            "annotations": {"summary": "CPU high on web-02"},
            "startsAt": "2024-01-15T10:05:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "panelURL": "http://grafana:3000/d/abc123/infra?viewPanel=2",
        },
    ],
}

RESOLVED_PAYLOAD = {
    "status": "resolved",
    "title": "[RESOLVED] HighCPU",
    "state": "ok",
    "alerts": [
        {
            "status": "resolved",
            "labels": {"alertname": "HighCPU", "instance": "web-01:9090", "severity": "critical"},
            "annotations": {"summary": "CPU recovered"},
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "2024-01-15T10:30:00.000Z",
            "dashboardURL": "http://grafana:3000/d/abc123/infra",
        }
    ],
}

MINIMAL_PAYLOAD = {
    "title": "[FIRING:1] Test",
    "state": "alerting",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "Test"},
            "annotations": {},
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }
    ],
}


# ─── Validation Tests ────────────────────────────────────


class TestGrafanaValidation:
    def setup_method(self):
        self.normalizer = GrafanaNormalizer()

    def test_valid_full_payload(self):
        assert self.normalizer.validate(FULL_PAYLOAD) is True

    def test_valid_minimal_payload(self):
        assert self.normalizer.validate(MINIMAL_PAYLOAD) is True

    def test_missing_alerts_key(self):
        assert self.normalizer.validate({"title": "Test", "state": "alerting"}) is False

    def test_empty_alerts_array(self):
        assert self.normalizer.validate({"alerts": [], "title": "Test"}) is False

    def test_alert_missing_alertname(self):
        payload = {
            "title": "Test",
            "alerts": [{"labels": {"severity": "critical"}}],
        }
        assert self.normalizer.validate(payload) is False

    def test_alert_missing_labels(self):
        payload = {"title": "Test", "alerts": [{"status": "firing"}]}
        assert self.normalizer.validate(payload) is False

    def test_prometheus_payload_rejected(self):
        """Prometheus payload lacks Grafana-specific fields."""
        prometheus_payload = {
            "version": "4",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Test", "severity": "critical"},
                    "annotations": {},
                    "startsAt": "2024-01-15T10:00:00.000Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                }
            ],
        }
        assert self.normalizer.validate(prometheus_payload) is False

    def test_splunk_payload_rejected(self):
        splunk = {"sid": "abc", "result": {"host": "web-01"}, "search_name": "Test"}
        assert self.normalizer.validate(splunk) is False


# ─── Normalization Tests ─────────────────────────────────


class TestGrafanaNormalization:
    def setup_method(self):
        self.normalizer = GrafanaNormalizer()

    def test_basic_fields(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert len(alerts) == 1

        alert = alerts[0]
        assert alert.name == "HighCPU"
        assert alert.source == "grafana"
        assert alert.severity == "critical"
        assert alert.status == "firing"
        assert alert.source_instance == "http://grafana:3000/"

    def test_description_from_annotations(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].description == "CPU usage is above 95% for 10 minutes"

    def test_description_falls_back_to_summary(self):
        payload = {
            "title": "Test",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test"},
                "annotations": {"summary": "Just a summary"},
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "dashboardURL": "http://grafana:3000/d/test",
            }],
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].description == "Just a summary"

    def test_host_extracted_from_instance(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].host == "web-01"

    def test_service_extracted_from_job(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].service == "node"

    def test_environment_extracted(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].environment == "production"

    def test_generator_url_prefers_dashboard_url(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].generator_url == "http://grafana:3000/d/abc123/infrastructure"

    def test_generator_url_falls_back_to_panel_url(self):
        payload = {
            "title": "Test",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test"},
                "annotations": {},
                "panelURL": "http://grafana:3000/d/test?viewPanel=1",
            }],
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].generator_url == "http://grafana:3000/d/test?viewPanel=1"

    def test_runbook_in_annotations(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].annotations["runbook_url"] == "https://runbooks.example.com/cpu"

    def test_value_string_in_annotations(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert "valueString" in alerts[0].annotations
        assert "95.3" in alerts[0].annotations["valueString"]

    def test_starts_at_parsed(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].starts_at is not None
        assert alerts[0].starts_at.year == 2024

    def test_zero_ends_at_is_none(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].ends_at is None

    def test_raw_payload_preserved(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].raw_payload is not None
        assert "labels" in alerts[0].raw_payload

    def test_extracted_labels_removed_from_clean_labels(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        labels = alerts[0].labels
        assert "alertname" not in labels
        assert "severity" not in labels
        assert "env" not in labels
        # But instance, job, grafana_folder should remain
        assert "instance" in labels
        assert "job" in labels
        assert "grafana_folder" in labels


# ─── Batch Tests ─────────────────────────────────────────


class TestGrafanaBatch:
    def setup_method(self):
        self.normalizer = GrafanaNormalizer()

    def test_multiple_alerts_in_batch(self):
        alerts = self.normalizer.normalize(BATCH_PAYLOAD)
        assert len(alerts) == 2

    def test_batch_alerts_have_different_hosts(self):
        alerts = self.normalizer.normalize(BATCH_PAYLOAD)
        hosts = {a.host for a in alerts}
        assert hosts == {"web-01", "web-02"}

    def test_batch_alerts_have_different_severities(self):
        alerts = self.normalizer.normalize(BATCH_PAYLOAD)
        severities = {a.severity for a in alerts}
        assert severities == {"critical", "warning"}


# ─── Resolved Alert Tests ────────────────────────────────


class TestGrafanaResolved:
    def setup_method(self):
        self.normalizer = GrafanaNormalizer()

    def test_resolved_status(self):
        alerts = self.normalizer.normalize(RESOLVED_PAYLOAD)
        assert alerts[0].status == "resolved"

    def test_resolved_ends_at(self):
        alerts = self.normalizer.normalize(RESOLVED_PAYLOAD)
        assert alerts[0].ends_at is not None
        assert alerts[0].ends_at.year == 2024


# ─── Severity Mapping Tests ──────────────────────────────


class TestGrafanaSeverityMapping:
    def setup_method(self):
        self.normalizer = GrafanaNormalizer()

    def _make_payload(self, severity_value: str, label_key: str = "severity"):
        return {
            "title": "Test",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test", label_key: severity_value},
                "annotations": {},
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "dashboardURL": "http://grafana:3000/d/test",
            }],
        }

    def test_critical(self):
        alerts = self.normalizer.normalize(self._make_payload("critical"))
        assert alerts[0].severity == "critical"

    def test_error_maps_to_critical(self):
        alerts = self.normalizer.normalize(self._make_payload("error"))
        assert alerts[0].severity == "critical"

    def test_warning(self):
        alerts = self.normalizer.normalize(self._make_payload("warning"))
        assert alerts[0].severity == "warning"

    def test_info(self):
        alerts = self.normalizer.normalize(self._make_payload("info"))
        assert alerts[0].severity == "info"

    def test_unknown_defaults_to_warning(self):
        alerts = self.normalizer.normalize(self._make_payload("banana"))
        assert alerts[0].severity == "warning"

    def test_priority_label_key(self):
        alerts = self.normalizer.normalize(self._make_payload("critical", "priority"))
        assert alerts[0].severity == "critical"

    def test_no_severity_label_defaults_to_warning(self):
        payload = {
            "title": "Test",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test"},
                "annotations": {},
                "dashboardURL": "http://grafana:3000/d/test",
            }],
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].severity == "warning"
