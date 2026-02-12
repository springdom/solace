from backend.core.silence import _matches
from backend.integrations import NormalizedAlert


def _make_alert(
    name: str = "TestAlert",
    service: str | None = "api",
    severity: str = "critical",
    labels: dict | None = None,
) -> NormalizedAlert:
    return NormalizedAlert(
        name=name,
        source="test",
        service=service,
        severity=severity,
        labels=labels or {},
    )


# ─── Matcher Logic Tests ────────────────────────────────


class TestMatcherLogic:
    def test_empty_matchers_match_everything(self):
        assert _matches({}, _make_alert()) is True

    def test_service_matcher_matches(self):
        assert _matches({"service": ["api", "web"]}, _make_alert(service="api")) is True

    def test_service_matcher_no_match(self):
        assert _matches({"service": ["web"]}, _make_alert(service="api")) is False

    def test_service_matcher_alert_no_service(self):
        assert _matches({"service": ["api"]}, _make_alert(service=None)) is False

    def test_severity_matcher_matches(self):
        matchers = {"severity": ["critical", "high"]}
        assert _matches(matchers, _make_alert(severity="critical")) is True

    def test_severity_matcher_no_match(self):
        assert _matches({"severity": ["low", "info"]}, _make_alert(severity="critical")) is False

    def test_label_matcher_matches(self):
        matchers = {"labels": {"env": "staging"}}
        alert = _make_alert(labels={"env": "staging", "team": "ops"})
        assert _matches(matchers, alert) is True

    def test_label_matcher_no_match(self):
        matchers = {"labels": {"env": "staging"}}
        alert = _make_alert(labels={"env": "production"})
        assert _matches(matchers, alert) is False

    def test_label_matcher_missing_key(self):
        matchers = {"labels": {"env": "staging"}}
        alert = _make_alert(labels={"team": "ops"})
        assert _matches(matchers, alert) is False

    def test_combined_matchers_all_must_match(self):
        matchers = {
            "service": ["api"],
            "severity": ["critical"],
            "labels": {"env": "staging"},
        }
        alert = _make_alert(
            service="api",
            severity="critical",
            labels={"env": "staging"},
        )
        assert _matches(matchers, alert) is True

    def test_combined_matchers_partial_match_fails(self):
        """Service matches but severity doesn't."""
        matchers = {
            "service": ["api"],
            "severity": ["low"],
        }
        alert = _make_alert(service="api", severity="critical")
        assert _matches(matchers, alert) is False

    def test_empty_service_list_matches_everything(self):
        """An empty list should be treated like no matcher."""
        assert _matches({"service": []}, _make_alert(service="api")) is True

    def test_empty_severity_list_matches_everything(self):
        assert _matches({"severity": []}, _make_alert(severity="critical")) is True

    def test_empty_labels_dict_matches_everything(self):
        assert _matches({"labels": {}}, _make_alert(labels={"env": "prod"})) is True

    def test_multiple_label_matchers_all_must_match(self):
        matchers = {"labels": {"env": "staging", "team": "ops"}}
        alert_match = _make_alert(labels={"env": "staging", "team": "ops", "extra": "val"})
        alert_partial = _make_alert(labels={"env": "staging", "team": "dev"})
        assert _matches(matchers, alert_match) is True
        assert _matches(matchers, alert_partial) is False
