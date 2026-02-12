"""Grafana webhook alert normalizer.

Grafana Unified Alerting sends alerts via webhook contact points.
Each webhook can contain multiple alerts grouped by the alert rule.

Example payload (Grafana Alerting v2):
{
  "receiver": "solace",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPU",
        "grafana_folder": "Infrastructure",
        "severity": "critical"
      },
      "annotations": {
        "summary": "CPU is high",
        "description": "CPU usage > 95%",
        "runbook_url": "https://runbooks.example.com/cpu"
      },
      "startsAt": "2024-01-15T10:00:00.000Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://grafana:3000/alerting/...",
      "fingerprint": "abc123",
      "silenceURL": "http://grafana:3000/alerting/silence/...",
      "dashboardURL": "http://grafana:3000/d/abc123/...",
      "panelURL": "http://grafana:3000/d/abc123/...?viewPanel=1",
      "valueString": "[ var='A' labels={instance=web-01} value=95.3 ]"
    }
  ],
  "groupLabels": {"alertname": "HighCPU"},
  "commonLabels": {"alertname": "HighCPU"},
  "commonAnnotations": {},
  "externalURL": "http://grafana:3000/",
  "version": "1",
  "groupKey": "{}:{alertname=\"HighCPU\"}",
  "truncatedAlerts": 0,
  "title": "[FIRING:1] HighCPU",
  "state": "alerting",
  "message": "CPU is high"
}

Docs: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
"""

from datetime import datetime

from backend.integrations import BaseNormalizer, NormalizedAlert

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
}

SEVERITY_LABEL_KEYS = ["severity", "priority", "level"]

# Grafana uses "0001-01-01T00:00:00Z" for unresolved alerts (same as Prometheus)
GRAFANA_ZERO_TIME = "0001-01-01T00:00:00Z"

# Fields unique to Grafana webhooks (not in Prometheus Alertmanager)
GRAFANA_SPECIFIC_FIELDS = {"dashboardURL", "panelURL", "silenceURL", "valueString"}


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse a Grafana timestamp string, returning None for zero/missing values."""
    if not ts or ts == GRAFANA_ZERO_TIME:
        return None
    try:
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _extract_severity(labels: dict) -> str:
    """Extract and normalize severity from Grafana labels."""
    for key in SEVERITY_LABEL_KEYS:
        value = labels.get(key, "").lower().strip()
        if value in SEVERITY_MAP:
            return SEVERITY_MAP[value]
    return "warning"


def _extract_service(labels: dict) -> str | None:
    """Extract service name from common Grafana label patterns."""
    for key in ["service", "app", "application", "job", "namespace"]:
        if key in labels:
            return labels[key]
    return None


def _extract_host(labels: dict) -> str | None:
    """Extract host/instance from Grafana labels."""
    instance = labels.get("instance", "")
    if instance:
        return instance.split(":")[0] if ":" in instance else instance
    return labels.get("node", labels.get("host", None))


def _extract_environment(labels: dict) -> str | None:
    """Extract environment from Grafana labels."""
    for key in ["environment", "env", "tier", "stage"]:
        if key in labels:
            return labels[key]
    return None


class GrafanaNormalizer(BaseNormalizer):
    """Normalizes Grafana webhook alert payloads.

    Handles the Unified Alerting webhook format. Each webhook can
    contain multiple alerts, similar to Prometheus Alertmanager.
    """

    def validate(self, payload: dict) -> bool:
        """Check that this looks like a Grafana webhook payload.

        Grafana webhooks share the same base structure as Prometheus
        (alerts array with labels), but include Grafana-specific fields
        like dashboardURL, panelURL, or top-level state/title/message.
        """
        if "alerts" not in payload or not isinstance(payload["alerts"], list):
            return False
        if len(payload["alerts"]) == 0:
            return False

        # Each alert must have labels with alertname
        for alert in payload["alerts"]:
            if "labels" not in alert or "alertname" not in alert.get("labels", {}):
                return False

        # Distinguish from Prometheus: check for Grafana-specific fields
        has_grafana_top_level = bool(
            payload.get("state") or payload.get("title") or payload.get("message")
        )
        has_grafana_alert_fields = any(
            key in alert
            for alert in payload["alerts"]
            for key in GRAFANA_SPECIFIC_FIELDS
        )

        return has_grafana_top_level or has_grafana_alert_fields

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Transform Grafana webhook into list of NormalizedAlerts."""
        normalized = []
        external_url = payload.get("externalURL", "")

        for alert_data in payload["alerts"]:
            labels = alert_data.get("labels", {})
            annotations = alert_data.get("annotations", {})

            alert_name = labels.get("alertname", "UnnamedAlert")
            status = alert_data.get("status", "firing")
            severity = _extract_severity(labels)

            service = _extract_service(labels)
            host = _extract_host(labels)
            environment = _extract_environment(labels)

            description = (
                annotations.get("description")
                or annotations.get("summary")
                or annotations.get("message")
            )

            starts_at = _parse_timestamp(alert_data.get("startsAt"))
            ends_at = _parse_timestamp(alert_data.get("endsAt"))

            # Prefer dashboardURL, fall back to panelURL, then generatorURL
            generator_url = (
                alert_data.get("dashboardURL")
                or alert_data.get("panelURL")
                or alert_data.get("generatorURL")
            )

            # Build clean labels — remove already-extracted fields
            extracted_keys = {
                "alertname", "severity", "priority", "level",
                "service", "app", "application",
                "environment", "env", "tier", "stage",
            }
            clean_labels = {k: v for k, v in labels.items() if k not in extracted_keys}

            # Include valueString in annotations if present
            clean_annotations = dict(annotations)
            value_string = alert_data.get("valueString")
            if value_string:
                clean_annotations["valueString"] = value_string

            normalized.append(
                NormalizedAlert(
                    name=alert_name,
                    source="grafana",
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
