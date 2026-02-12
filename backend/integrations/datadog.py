"""Datadog webhook alert normalizer.

Datadog sends a webhook with a JSON payload when a monitor triggers.
Datadog uses $-variable templates that get substituted before delivery,
so the normalizer receives final values.

Example payload (after variable substitution):
{
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
  "link": "https://app.datadoghq.com/event/event?id=123456"
}

Docs: https://docs.datadoghq.com/integrations/webhooks/
"""

import re
from datetime import UTC, datetime

from backend.integrations import BaseNormalizer, NormalizedAlert

# Datadog priority to Solace severity
PRIORITY_MAP = {
    "p1": "critical",
    "p2": "high",
    "p3": "warning",
    "p4": "low",
    "p5": "info",
}

# Datadog alert_type to severity (fallback when no priority)
ALERT_TYPE_MAP = {
    "error": "critical",
    "warning": "warning",
    "info": "info",
    "success": "info",
}

# Datadog transition states to Solace status
STATUS_MAP = {
    "triggered": "firing",
    "re-triggered": "firing",
    "recovered": "resolved",
    "no data": "firing",
    "warn": "firing",
}

# Regex to strip status prefix from title: [Triggered], [Recovered], etc.
TITLE_PREFIX_RE = re.compile(
    r"^\[(?:Triggered|Recovered|Re-Triggered|No Data|Warn)\]\s*",
    re.IGNORECASE,
)


def _extract_severity(payload: dict) -> str:
    """Extract severity from priority field, then alert_type as fallback."""
    priority = payload.get("priority", "").lower().strip()
    if priority in PRIORITY_MAP:
        return PRIORITY_MAP[priority]

    alert_type = payload.get("alert_type", "").lower().strip()
    if alert_type in ALERT_TYPE_MAP:
        return ALERT_TYPE_MAP[alert_type]

    return "warning"


def _extract_status(payload: dict) -> str:
    """Map Datadog alert_transition to Solace status."""
    transition = payload.get("alert_transition", "").lower().strip()
    return STATUS_MAP.get(transition, "firing")


def _parse_tags(tags_str: str) -> dict:
    """Parse Datadog tags string into a dict.

    Datadog tags are comma-separated key:value pairs.
    Tags without a colon are stored with an empty string value.
    """
    if not tags_str or not tags_str.strip():
        return {}

    result = {}
    for tag in tags_str.split(","):
        tag = tag.strip()
        if not tag:
            continue
        if ":" in tag:
            key, _, value = tag.partition(":")
            result[key.strip()] = value.strip()
        else:
            result[tag] = ""
    return result


def _clean_title(title: str) -> str:
    """Strip Datadog status prefix from title."""
    return TITLE_PREFIX_RE.sub("", title).strip()


class DatadogNormalizer(BaseNormalizer):
    """Normalizes Datadog webhook alert payloads.

    Datadog sends one alert per webhook. The payload contains
    monitor metadata, tags, and the alert transition state.
    """

    def validate(self, payload: dict) -> bool:
        """Check that this looks like a Datadog webhook payload."""
        if "title" not in payload:
            return False
        # Must have alert_transition or alert_type (Datadog-specific fields)
        if "alert_transition" not in payload and "alert_type" not in payload:
            return False
        return True

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Transform a Datadog webhook payload into a NormalizedAlert."""
        title = payload.get("title", "Datadog Alert")
        name = _clean_title(title)

        severity = _extract_severity(payload)
        status = _extract_status(payload)

        # Parse tags into labels, extract service and environment
        tags = _parse_tags(payload.get("tags", ""))
        service = tags.pop("service", None)
        environment = tags.pop("env", None) or tags.pop("environment", None)

        host = payload.get("hostname")
        description = payload.get("text")
        generator_url = payload.get("url") or payload.get("link")

        # Timestamp from epoch
        starts_at = None
        date_val = payload.get("date")
        if date_val:
            try:
                starts_at = datetime.fromtimestamp(int(date_val), tz=UTC)
            except (ValueError, TypeError, OSError):
                pass

        # Build labels from tags + Datadog metadata
        labels = dict(tags)
        if payload.get("alert_id"):
            labels["datadog_alert_id"] = str(payload["alert_id"])
        if payload.get("event_type"):
            labels["datadog_event_type"] = payload["event_type"]
        org = payload.get("org")
        if isinstance(org, dict) and org.get("name"):
            labels["datadog_org"] = org["name"]

        # Annotations
        annotations: dict[str, str] = {}
        if payload.get("link"):
            annotations["event_link"] = payload["link"]

        return [
            NormalizedAlert(
                name=name,
                source="datadog",
                severity=severity,
                status=status,
                description=description,
                service=service,
                environment=environment,
                host=host,
                labels=labels,
                annotations=annotations,
                starts_at=starts_at,
                generator_url=generator_url,
                raw_payload=payload,
            )
        ]
