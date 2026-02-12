"""Tests for the Splunk webhook normalizer."""

from backend.integrations.splunk import SplunkNormalizer

BASIC_PAYLOAD = {
    "result": {
        "sourcetype": "syslog",
        "host": "web-01",
        "count": "847",
    },
    "sid": "scheduler_admin_search_W2_at_14232356_132",
    "results_link": "http://splunk.example.com:8000/app/search/@go?sid=scheduler_admin_search_W2",
    "search_name": "High CPU Usage Alert",
    "owner": "admin",
    "app": "search",
}

RICH_PAYLOAD = {
    "result": {
        "host": "db-primary-01",
        "severity": "critical",
        "service": "postgres",
        "environment": "production",
        "message": "Replication lag exceeds 30 seconds",
        "sourcetype": "dbmon",
        "lag_seconds": "47.2",
        "db_name": "users",
    },
    "sid": "scheduler_admin_DBReplicationLag_at_17000000_001",
    "results_link": "http://splunk:8000/app/db_monitoring/@go?sid=scheduler_admin_DBReplicationLag",
    "search_name": "DB Replication Lag Critical",
    "owner": "dba_team",
    "app": "db_monitoring",
}

MINIMAL_PAYLOAD = {
    "result": {},
    "sid": "rt_scheduler_admin_search_W2_at_14232356_132",
}

ES_NOTABLE_PAYLOAD = {
    "result": {
        "dest": "10.0.1.50",
        "src": "192.168.1.100",
        "urgency": "urgent",
        "rule_name": "Brute Force Login Attempt",
        "description": "Multiple failed logins detected from 192.168.1.100",
        "app": "SplunkEnterpriseSecuritySuite",
        "sourcetype": "linux:auth",
        "user": "root",
        "action": "failure",
    },
    "sid": "scheduler_nobody_SplunkEnterpriseSecuritySuite_RMD5f2c0_at_17000000_1",
    "results_link": "http://splunk:8000/app/SplunkEnterpriseSecuritySuite/@go?sid=...",
    "search_name": "Brute Force Login Attempt",
    "owner": "nobody",
    "app": "SplunkEnterpriseSecuritySuite",
}

RISK_SCORE_PAYLOAD = {
    "result": {
        "host": "endpoint-42",
        "risk_score": "85",
        "service_name": "vpn-gateway",
        "msg": "Unusual outbound traffic volume detected",
    },
    "sid": "scheduler_admin_risk_alert_001",
    "results_link": "http://splunk:8000/app/search/@go?sid=risk_001",
    "search_name": "High Risk Score Alert",
    "owner": "admin",
    "app": "risk_analysis",
}


class TestSplunkValidation:
    def test_valid_basic(self):
        n = SplunkNormalizer()
        assert n.validate(BASIC_PAYLOAD) is True

    def test_valid_minimal(self):
        n = SplunkNormalizer()
        assert n.validate(MINIMAL_PAYLOAD) is True

    def test_invalid_no_sid(self):
        n = SplunkNormalizer()
        assert n.validate({"result": {}, "search_name": "test"}) is False

    def test_invalid_no_result(self):
        n = SplunkNormalizer()
        assert n.validate({"sid": "test123"}) is False

    def test_invalid_result_not_dict(self):
        n = SplunkNormalizer()
        assert n.validate({"sid": "test123", "result": "not a dict"}) is False

    def test_invalid_empty(self):
        n = SplunkNormalizer()
        assert n.validate({}) is False

    def test_rejects_prometheus_payload(self):
        """Ensure Splunk normalizer doesn't match Prometheus payloads."""
        n = SplunkNormalizer()
        prometheus_payload = {
            "version": "4",
            "alerts": [{"labels": {"alertname": "test"}}],
        }
        assert n.validate(prometheus_payload) is False


class TestSplunkNormalization:
    def test_basic_payload(self):
        n = SplunkNormalizer()
        alerts = n.normalize(BASIC_PAYLOAD)
        assert len(alerts) == 1

        a = alerts[0]
        assert a.name == "High CPU Usage Alert"
        assert a.source == "splunk"
        assert a.status == "firing"
        assert a.host == "web-01"
        assert a.severity == "warning"  # no severity field, defaults
        assert a.generator_url == BASIC_PAYLOAD["results_link"]
        assert a.raw_payload == BASIC_PAYLOAD

    def test_rich_payload_extracts_all_fields(self):
        n = SplunkNormalizer()
        alerts = n.normalize(RICH_PAYLOAD)
        a = alerts[0]

        assert a.name == "DB Replication Lag Critical"
        assert a.severity == "critical"
        assert a.service == "postgres"
        assert a.host == "db-primary-01"
        assert a.environment == "production"
        assert a.description == "Replication lag exceeds 30 seconds"
        assert a.source == "splunk"

    def test_rich_payload_labels(self):
        """Non-extracted fields should go into labels."""
        n = SplunkNormalizer()
        a = n.normalize(RICH_PAYLOAD)[0]

        # These were extracted into structured fields, should NOT be in labels
        assert "host" not in a.labels
        assert "severity" not in a.labels
        assert "service" not in a.labels
        assert "environment" not in a.labels
        assert "message" not in a.labels

        # Remaining result fields should be in labels
        assert a.labels["lag_seconds"] == "47.2"
        assert a.labels["db_name"] == "users"

        # Splunk metadata in labels
        assert a.labels["splunk_owner"] == "dba_team"
        assert a.labels["splunk_app"] == "db_monitoring"

    def test_minimal_payload_defaults(self):
        n = SplunkNormalizer()
        alerts = n.normalize(MINIMAL_PAYLOAD)
        a = alerts[0]

        assert "Splunk Alert" in a.name
        assert a.severity == "warning"
        assert a.status == "firing"
        assert a.host is None
        assert a.service is None
        assert a.description is None

    def test_es_notable_urgency_mapping(self):
        """Enterprise Security uses 'urgency' field with 'urgent' value."""
        n = SplunkNormalizer()
        a = n.normalize(ES_NOTABLE_PAYLOAD)[0]

        assert a.severity == "critical"  # urgent -> critical
        assert a.host == "10.0.1.50"  # from 'dest' field
        assert a.service == "SplunkEnterpriseSecuritySuite"  # from 'app' field
        assert a.description == "Multiple failed logins detected from 192.168.1.100"
        assert a.name == "Brute Force Login Attempt"

    def test_risk_score_severity(self):
        """Numeric risk_score should map to severity."""
        n = SplunkNormalizer()
        a = n.normalize(RISK_SCORE_PAYLOAD)[0]

        assert a.severity == "critical"  # risk_score 85 >= 80
        assert a.host == "endpoint-42"
        assert a.service == "vpn-gateway"  # from service_name field
        assert a.description == "Unusual outbound traffic volume detected"

    def test_annotations_contain_results_link(self):
        n = SplunkNormalizer()
        a = n.normalize(BASIC_PAYLOAD)[0]
        assert a.annotations["results_link"] == BASIC_PAYLOAD["results_link"]

    def test_no_results_link(self):
        payload = {
            "result": {"host": "test"},
            "sid": "test123",
        }
        n = SplunkNormalizer()
        a = n.normalize(payload)[0]
        assert "results_link" not in a.annotations
        assert a.generator_url is None

    def test_underscored_fields_excluded_from_labels(self):
        """Splunk internal fields starting with _ should not be in labels."""
        payload = {
            "result": {
                "host": "web-01",
                "_raw": "Jan 15 10:00:00 web-01 kernel: CPU high",
                "_time": "1705305600",
                "_serial": "0",
                "sourcetype": "syslog",
            },
            "sid": "test_sid",
            "search_name": "Test",
        }
        n = SplunkNormalizer()
        a = n.normalize(payload)[0]

        # _raw is in DESCRIPTION_FIELD_KEYS so it gets extracted as description
        # _time and _serial should be excluded from labels
        assert "_time" not in a.labels
        assert "_serial" not in a.labels
        assert "_raw" not in a.labels


class TestSeverityMapping:
    """Test various severity value mappings."""

    def _make_payload(self, severity_field: str, severity_value: str) -> dict:
        return {
            "result": {severity_field: severity_value},
            "sid": "test",
            "search_name": "Test",
        }

    def test_standard_values(self):
        n = SplunkNormalizer()
        assert n.normalize(self._make_payload("severity", "critical"))[0].severity == "critical"
        assert n.normalize(self._make_payload("severity", "high"))[0].severity == "high"
        assert n.normalize(self._make_payload("severity", "warning"))[0].severity == "warning"
        assert n.normalize(self._make_payload("severity", "low"))[0].severity == "low"
        assert n.normalize(self._make_payload("severity", "info"))[0].severity == "info"

    def test_alternative_field_names(self):
        n = SplunkNormalizer()
        assert n.normalize(self._make_payload("priority", "critical"))[0].severity == "critical"
        assert n.normalize(self._make_payload("urgency", "high"))[0].severity == "high"
        assert n.normalize(self._make_payload("level", "warning"))[0].severity == "warning"

    def test_es_urgency_values(self):
        n = SplunkNormalizer()
        assert n.normalize(self._make_payload("urgency", "urgent"))[0].severity == "critical"

    def test_numeric_risk_scores(self):
        n = SplunkNormalizer()
        assert n.normalize(self._make_payload("risk_score", "90"))[0].severity == "critical"
        assert n.normalize(self._make_payload("risk_score", "65"))[0].severity == "high"
        assert n.normalize(self._make_payload("risk_score", "45"))[0].severity == "warning"
        assert n.normalize(self._make_payload("risk_score", "25"))[0].severity == "low"
        assert n.normalize(self._make_payload("risk_score", "10"))[0].severity == "info"

    def test_unknown_severity_defaults(self):
        n = SplunkNormalizer()
        assert n.normalize(self._make_payload("severity", "banana"))[0].severity == "warning"
