"""Splunk webhook alert normalizer.

Splunk sends a minimal JSON payload when a saved search triggers a webhook alert action.
The payload contains metadata about the search plus the first result row.

Example payload:
{
    "result": {
        "sourcetype": "syslog",
        "host": "web-01",
        "source": "/var/log/messages",
        "count": "847",
        "avg_cpu": "95.3"
    },
    "sid": "scheduler_admin_search_W2_at_14232356_132",
    "results_link": "http://splunk.example.com:8000/app/search/@go?sid=scheduler_admin_...",
    "search_name": "High CPU Usage Alert",
    "owner": "admin",
    "app": "search"
}

Key considerations:
- Only the FIRST result row is included in "result" — Splunk does not batch alerts
- Field names in "result" are entirely determined by the SPL query, so we check
  common patterns (host, severity, service, src_host, dest, etc.)
- search_name is the primary alert identifier
- results_link provides a direct link back to the Splunk search results
- There is no native severity or status field — we infer from result fields
  or default to "warning"

Docs: https://help.splunk.com/en/splunk-enterprise/alert-and-respond/alerting-manual/
      9.1/configure-alert-actions/use-a-webhook-alert-action
"""

from backend.integrations import BaseNormalizer, NormalizedAlert

# Splunk has no standard severity field — teams use various field names
# in their saved searches. We check these in order of priority.
SEVERITY_FIELD_KEYS = [
    "severity", "priority", "urgency", "level",
    "alert_severity", "risk_level", "risk_score",
]

SEVERITY_MAP = {
    # Standard names
    "critical": "critical",
    "crit": "critical",
    "high": "high",
    "major": "high",
    "medium": "warning",
    "warning": "warning",
    "warn": "warning",
    "low": "low",
    "minor": "low",
    "info": "info",
    "informational": "info",
    # Splunk Enterprise Security urgency values
    "urgent": "critical",
    # Numeric risk scores (as strings from Splunk)
    "5": "critical",
    "4": "high",
    "3": "warning",
    "2": "low",
    "1": "info",
}

# Fields that commonly contain the host/instance
HOST_FIELD_KEYS = [
    "host", "hostname", "src_host", "dest", "dest_host",
    "dvc", "dvc_host", "computer", "node", "instance",
    "ComputerName", "server", "src", "src_ip",
]

# Fields that commonly contain the service name
SERVICE_FIELD_KEYS = [
    "service", "app", "application", "service_name",
    "sourcetype", "index", "source_app",
]

# Fields that commonly contain environment info
ENV_FIELD_KEYS = [
    "environment", "env", "tier", "stage", "datacenter", "dc", "region",
]

# Fields that might contain a description or message
DESCRIPTION_FIELD_KEYS = [
    "message", "msg", "description", "summary", "reason",
    "details", "alert_message", "comment", "latest_error", "_raw",
]


def _extract_from_result(result: dict, field_keys: list[str]) -> str | None:
    """Try to extract a value from result using a list of possible field names."""
    for key in field_keys:
        value = result.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _extract_severity(result: dict) -> str:
    """Extract and normalize severity from Splunk result fields."""
    raw = _extract_from_result(result, SEVERITY_FIELD_KEYS)
    if raw:
        normalized = SEVERITY_MAP.get(raw.lower().strip())
        if normalized:
            return normalized
        # Try numeric risk_score ranges
        try:
            score = float(raw)
            if score >= 80:
                return "critical"
            if score >= 60:
                return "high"
            if score >= 40:
                return "warning"
            if score >= 20:
                return "low"
            return "info"
        except (ValueError, TypeError):
            pass
    return "warning"


def _build_labels(result: dict, extracted_keys: set[str]) -> dict:
    """Build a clean label set from result fields we haven't already extracted."""
    labels = {}
    for k, v in result.items():
        if k not in extracted_keys and v and str(v).strip():
            # Skip internal Splunk fields starting with underscore
            if not k.startswith("_"):
                labels[k] = str(v)
    return labels


class SplunkNormalizer(BaseNormalizer):
    """Normalizes Splunk webhook alert payloads.

    Since Splunk's webhook payload is minimal and field names depend
    on the SPL query, this normalizer uses heuristics to extract
    structured fields from common naming patterns.
    """

    def validate(self, payload: dict) -> bool:
        """Check that this looks like a Splunk webhook payload."""
        # Must have sid (search ID) — this is always present
        if "sid" not in payload:
            return False
        # Must have result dict (even if empty)
        if "result" not in payload or not isinstance(payload.get("result"), dict):
            return False
        return True

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Transform a Splunk webhook payload into a NormalizedAlert.

        Splunk webhooks always produce exactly one alert (they only
        include the first result row).
        """
        result = payload.get("result", {})
        sid = payload.get("sid", "")
        search_name = payload.get("search_name")
        results_link = payload.get("results_link")
        owner = payload.get("owner")
        app = payload.get("app")

        # Alert name: prefer search_name, fall back to SID
        name = search_name or f"Splunk Alert ({sid[:20]}...)" if sid else "Splunk Alert"

        # Extract structured fields from result
        severity = _extract_severity(result)
        host = _extract_from_result(result, HOST_FIELD_KEYS)
        service = _extract_from_result(result, SERVICE_FIELD_KEYS)
        environment = _extract_from_result(result, ENV_FIELD_KEYS)
        description = _extract_from_result(result, DESCRIPTION_FIELD_KEYS)

        # Track which fields we extracted so we can put the rest in labels
        extracted_keys: set[str] = set()
        for key_list in [
            SEVERITY_FIELD_KEYS, HOST_FIELD_KEYS,
            SERVICE_FIELD_KEYS, ENV_FIELD_KEYS, DESCRIPTION_FIELD_KEYS,
        ]:
            for key in key_list:
                if key in result:
                    extracted_keys.add(key)

        # Build labels from remaining result fields
        labels = _build_labels(result, extracted_keys)

        # Add Splunk-specific metadata to labels
        if owner:
            labels["splunk_owner"] = owner
        if app:
            labels["splunk_app"] = app
        if sid:
            labels["splunk_sid"] = sid

        # Annotations
        annotations: dict[str, str] = {}
        if results_link:
            annotations["results_link"] = results_link

        return [
            NormalizedAlert(
                name=name,
                source="splunk",
                source_instance=results_link,
                severity=severity,
                status="firing",  # Splunk webhooks only fire on trigger, no resolve
                description=description,
                service=service,
                environment=environment,
                host=host,
                labels=labels,
                annotations=annotations,
                generator_url=results_link,
                raw_payload=payload,
            )
        ]
