from backend.integrations.prometheus import PrometheusNormalizer

# ─── Fixtures ────────────────────────────────────────────

FULL_PAYLOAD = {
    "version": "4",
    "groupKey": '{}:{alertname="HighCPU"}',
    "truncatedAlerts": 0,
    "status": "firing",
    "receiver": "solace",
    "groupLabels": {"alertname": "HighCPU"},
    "commonLabels": {"alertname": "HighCPU", "severity": "critical"},
    "commonAnnotations": {"summary": "CPU is high"},
    "externalURL": "http://alertmanager:9093",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighCPU",
                "instance": "web-01:9090",
                "job": "node",
                "severity": "critical",
                "env": "production",
            },
            "annotations": {
                "summary": "High CPU usage on web-01",
                "description": "CPU usage is above 95% for 10 minutes",
                "runbook_url": "https://runbooks.example.com/cpu",
            },
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=up",
            "fingerprint": "abc123def456",
        }
    ],
}

BATCH_PAYLOAD = {
    "version": "4",
    "groupKey": '{}:{alertname="HighCPU"}',
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "HighCPU", "instance": "web-01:9090", "severity": "critical"},
            "annotations": {"summary": "CPU high on web-01"},
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
        },
        {
            "status": "firing",
            "labels": {"alertname": "HighCPU", "instance": "web-02:9090", "severity": "warning"},
            "annotations": {"summary": "CPU high on web-02"},
            "startsAt": "2024-01-15T10:05:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
        },
    ],
}

RESOLVED_PAYLOAD = {
    "version": "4",
    "status": "resolved",
    "alerts": [
        {
            "status": "resolved",
            "labels": {"alertname": "HighCPU", "instance": "web-01:9090", "severity": "critical"},
            "annotations": {"summary": "CPU recovered"},
            "startsAt": "2024-01-15T10:00:00.000Z",
            "endsAt": "2024-01-15T10:30:00.000Z",
        }
    ],
}


# ─── Validation Tests ────────────────────────────────────


class TestPrometheusValidation:
    def setup_method(self):
        self.normalizer = PrometheusNormalizer()

    def test_valid_payload(self):
        assert self.normalizer.validate(FULL_PAYLOAD) is True

    def test_missing_alerts_key(self):
        assert self.normalizer.validate({"version": "4"}) is False

    def test_empty_alerts_array(self):
        assert self.normalizer.validate({"alerts": []}) is False

    def test_alert_missing_alertname(self):
        payload = {"alerts": [{"labels": {"severity": "critical"}}]}
        assert self.normalizer.validate(payload) is False

    def test_alert_missing_labels(self):
        payload = {"alerts": [{"status": "firing"}]}
        assert self.normalizer.validate(payload) is False

    def test_generic_payload_rejected(self):
        generic = {"name": "HighCPU", "severity": "critical"}
        assert self.normalizer.validate(generic) is False


# ─── Normalization Tests ─────────────────────────────────


class TestPrometheusNormalization:
    def setup_method(self):
        self.normalizer = PrometheusNormalizer()

    def test_basic_fields(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert len(alerts) == 1

        alert = alerts[0]
        assert alert.name == "HighCPU"
        assert alert.source == "prometheus"
        assert alert.severity == "critical"
        assert alert.status == "firing"
        assert alert.source_instance == "http://alertmanager:9093"

    def test_description_from_annotations(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].description == "CPU usage is above 95% for 10 minutes"

    def test_description_falls_back_to_summary(self):
        payload = {
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test"},
                "annotations": {"summary": "Just a summary"},
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }]
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].description == "Just a summary"

    def test_host_extracted_from_instance(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].host == "web-01"  # port stripped

    def test_service_extracted_from_job(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].service == "node"  # from job label

    def test_environment_extracted(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].environment == "production"

    def test_generator_url(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].generator_url == "http://prometheus:9090/graph?g0.expr=up"

    def test_runbook_in_annotations(self):
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        assert alerts[0].annotations["runbook_url"] == "https://runbooks.example.com/cpu"

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
        """Labels like alertname, severity, env should not appear in clean_labels."""
        alerts = self.normalizer.normalize(FULL_PAYLOAD)
        labels = alerts[0].labels
        assert "alertname" not in labels
        assert "severity" not in labels
        assert "env" not in labels
        # But instance and job should still be there
        assert "instance" in labels
        assert "job" in labels


# ─── Batch Tests ─────────────────────────────────────────


class TestPrometheusBatch:
    def setup_method(self):
        self.normalizer = PrometheusNormalizer()

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


class TestPrometheusResolved:
    def setup_method(self):
        self.normalizer = PrometheusNormalizer()

    def test_resolved_status(self):
        alerts = self.normalizer.normalize(RESOLVED_PAYLOAD)
        assert alerts[0].status == "resolved"

    def test_resolved_ends_at(self):
        alerts = self.normalizer.normalize(RESOLVED_PAYLOAD)
        assert alerts[0].ends_at is not None
        assert alerts[0].ends_at.year == 2024


# ─── Severity Mapping Tests ──────────────────────────────


class TestSeverityMapping:
    def setup_method(self):
        self.normalizer = PrometheusNormalizer()

    def _make_payload(self, severity_value: str, label_key: str = "severity"):
        return {
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test", label_key: severity_value},
                "annotations": {},
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }]
        }

    def test_critical(self):
        alerts = self.normalizer.normalize(self._make_payload("critical"))
        assert alerts[0].severity == "critical"

    def test_error_maps_to_critical(self):
        alerts = self.normalizer.normalize(self._make_payload("error"))
        assert alerts[0].severity == "critical"

    def test_page_maps_to_critical(self):
        alerts = self.normalizer.normalize(self._make_payload("page"))
        assert alerts[0].severity == "critical"

    def test_warning(self):
        alerts = self.normalizer.normalize(self._make_payload("warning"))
        assert alerts[0].severity == "warning"

    def test_ticket_maps_to_warning(self):
        alerts = self.normalizer.normalize(self._make_payload("ticket"))
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
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "Test"},
                "annotations": {},
                "startsAt": "2024-01-15T10:00:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }]
        }
        alerts = self.normalizer.normalize(payload)
        assert alerts[0].severity == "warning"
