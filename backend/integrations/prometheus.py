"""Prometheus Alertmanager webhook normalizer.

Prometheus Alertmanager sends grouped alerts as a single webhook POST.
The payload contains a list of alerts that share the same group key.

Example payload:
{
  "version": "4",
  "groupKey": "{}:{alertname=\"HighCPU\"}",
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
        "severity": "critical"
      },
      "annotations": {
        "summary": "High CPU usage on web-01",
        "description": "CPU usage is above 95% for 10 minutes",
        "runbook_url": "https://runbooks.example.com/cpu"
      },
      "startsAt": "2024-01-15T10:00:00.000Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph?g0.expr=...",
      "fingerprint": "abc123def456"
    }
  ]
}

Docs: https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
"""

from datetime import datetime

from backend.integrations import BaseNormalizer, NormalizedAlert

# Prometheus severity is not standardized — teams use different label names.
# We check common patterns and normalize to Solace's severity levels.
SEVERITY_MAP = {
    "critical": "critical",
    "error": "critical",
    "high": "high",
    "major": "high",
    "warning": "warning",
    "warn": "warning",
    "low": "low",
    "minor": "low",
    "info": "info",
    "informational": "info",
    "none": "info",
    "page": "critical",
    "ticket": "warning",
}

# Labels that commonly indicate severity
SEVERITY_LABEL_KEYS = ["severity", "priority", "level"]

# Zero time in Prometheus means "not resolved"
PROMETHEUS_ZERO_TIME = "0001-01-01T00:00:00Z"


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse a Prometheus timestamp string, returning None for zero/missing values."""
    if not ts or ts == PROMETHEUS_ZERO_TIME:
        return None
    try:
        # Handle both Z and +00:00 suffixes
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _extract_severity(labels: dict) -> str:
    """Extract and normalize severity from Prometheus labels."""
    for key in SEVERITY_LABEL_KEYS:
        value = labels.get(key, "").lower().strip()
        if value in SEVERITY_MAP:
            return SEVERITY_MAP[value]
    return "warning"  # default


def _extract_service(labels: dict) -> str | None:
    """Extract service name from common Prometheus label patterns."""
    for key in ["service", "app", "application", "job", "namespace"]:
        if key in labels:
            return labels[key]
    return None


def _extract_host(labels: dict) -> str | None:
    """Extract host/instance from Prometheus labels."""
    instance = labels.get("instance", "")
    if instance:
        # Strip port from instance (e.g., "web-01:9090" → "web-01")
        return instance.split(":")[0] if ":" in instance else instance
    return labels.get("node", labels.get("host", None))


def _extract_environment(labels: dict) -> str | None:
    """Extract environment from Prometheus labels."""
    for key in ["environment", "env", "tier", "stage"]:
        if key in labels:
            return labels[key]
    return None


class PrometheusNormalizer(BaseNormalizer):
    """Normalizes Prometheus Alertmanager webhook payloads.

    Handles the v4 webhook format. Each webhook can contain multiple
    alerts grouped by Alertmanager's group_by configuration.
    """

    def validate(self, payload: dict) -> bool:
        """Check that this looks like a Prometheus Alertmanager webhook."""
        # Must have alerts array and version
        if "alerts" not in payload or not isinstance(payload["alerts"], list):
            return False
        # Must have at least one alert
        if len(payload["alerts"]) == 0:
            return False
        # Each alert must have labels
        for alert in payload["alerts"]:
            if "labels" not in alert or "alertname" not in alert.get("labels", {}):
                return False
        return True

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Transform Prometheus webhook into list of NormalizedAlerts."""
        normalized = []
        external_url = payload.get("externalURL", "")

        for alert_data in payload["alerts"]:
            labels = alert_data.get("labels", {})
            annotations = alert_data.get("annotations", {})

            # Core fields
            alert_name = labels.get("alertname", "UnnamedAlert")
            status = alert_data.get("status", "firing")
            severity = _extract_severity(labels)

            # Extract structured fields from labels
            service = _extract_service(labels)
            host = _extract_host(labels)
            environment = _extract_environment(labels)

            # Description from annotations (check common keys)
            description = (
                annotations.get("description")
                or annotations.get("summary")
                or annotations.get("message")
            )

            # Timestamps
            starts_at = _parse_timestamp(alert_data.get("startsAt"))
            ends_at = _parse_timestamp(alert_data.get("endsAt"))

            # Generator URL (link back to Prometheus query)
            generator_url = alert_data.get("generatorURL")

            # Build clean label set — remove fields we've already extracted
            # to avoid duplication in the labels JSONB column
            extracted_keys = {
                "alertname", "severity", "priority", "level",
                "service", "app", "application",
                "environment", "env", "tier", "stage",
            }
            clean_labels = {k: v for k, v in labels.items() if k not in extracted_keys}

            # Build annotations — include runbook URL prominently
            clean_annotations = dict(annotations)
            if "runbook_url" in annotations:
                clean_annotations["runbook_url"] = annotations["runbook_url"]

            normalized.append(
                NormalizedAlert(
                    name=alert_name,
                    source="prometheus",
                    source_instance=external_url or None,
                    severity=severity,
                    status="firing" if status == "firing" else "resolved",
                    description=description,
                    service=service,
                    environment=environment,
                    host=host,
                    labels=clean_labels,
                    annotations=clean_annotations,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    generator_url=generator_url,
                    raw_payload=alert_data,
                )
            )

        return normalized
