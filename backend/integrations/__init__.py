"""Alert normalizers transform provider-specific payloads into Solace's internal format.

Each integration (Prometheus, Splunk, Grafana, etc.) has its own normalizer
that implements the BaseNormalizer interface. The generic normalizer handles
any JSON payload that conforms to Solace's webhook schema.

To add a new integration:
1. Create a new file in this directory (e.g., prometheus.py)
2. Implement a class that inherits from BaseNormalizer
3. Register it in the NORMALIZERS dict below
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from backend.schemas import GenericWebhookPayload


class NormalizedAlert:
    """Internal alert representation after normalization.

    This is the common format that all normalizers produce,
    regardless of the source system.
    """

    def __init__(
        self,
        name: str,
        source: str,
        severity: str = "warning",
        status: str = "firing",
        description: str | None = None,
        service: str | None = None,
        environment: str | None = None,
        host: str | None = None,
        labels: dict | None = None,
        annotations: dict | None = None,
        tags: list[str] | None = None,
        source_instance: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        generator_url: str | None = None,
        raw_payload: dict | None = None,
    ):
        self.name = name
        self.source = source
        self.severity = severity
        self.status = status
        self.description = description
        self.service = service
        self.environment = environment
        self.host = host
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.tags = tags or []
        self.source_instance = source_instance
        self.starts_at = starts_at or datetime.now(UTC)
        self.ends_at = ends_at
        self.generator_url = generator_url
        self.raw_payload = raw_payload


class BaseNormalizer(ABC):
    """Base class for all alert normalizers."""

    @abstractmethod
    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Transform a raw webhook payload into one or more NormalizedAlerts.

        Some providers (like Prometheus Alertmanager) send batched alerts
        in a single webhook, so this returns a list.
        """
        ...

    @abstractmethod
    def validate(self, payload: dict) -> bool:
        """Check if a payload is valid for this normalizer."""
        ...


class GenericNormalizer(BaseNormalizer):
    """Normalizer for the generic webhook format.

    Accepts any JSON payload that conforms to Solace's GenericWebhookPayload schema.
    This is the default normalizer and the easiest way to integrate any system.
    """

    def validate(self, payload: dict) -> bool:
        try:
            GenericWebhookPayload(**payload)
            return True
        except Exception:
            return False

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        data = GenericWebhookPayload(**payload)

        alert = NormalizedAlert(
            name=data.name,
            source=data.source,
            severity=data.severity.value,
            status=data.status.value,
            description=data.description,
            service=data.service,
            environment=data.environment,
            host=data.host,
            labels=data.labels,
            annotations=data.annotations,
            tags=data.tags,
            source_instance=data.source_instance,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            generator_url=data.generator_url,
            raw_payload=payload,
        )

        return [alert]


# ─── Normalizer Registry ─────────────────────────────────
# Add new normalizers here as they're implemented

NORMALIZERS: dict[str, BaseNormalizer] = {
    "generic": GenericNormalizer(),
    "prometheus": None,  # lazy-loaded below
    "splunk": None,      # lazy-loaded below
    "email": None,       # lazy-loaded below
    "grafana": None,     # lazy-loaded below
    "datadog": None,     # lazy-loaded below
}


def get_normalizer(provider: str) -> BaseNormalizer:
    """Get the normalizer for a given provider."""
    if provider not in NORMALIZERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {', '.join(NORMALIZERS.keys())}"
        )

    # Lazy-load to avoid circular imports
    if NORMALIZERS[provider] is None:
        if provider == "prometheus":
            from backend.integrations.prometheus import PrometheusNormalizer
            NORMALIZERS[provider] = PrometheusNormalizer()
        elif provider == "splunk":
            from backend.integrations.splunk import SplunkNormalizer
            NORMALIZERS[provider] = SplunkNormalizer()
        elif provider == "email":
            from backend.integrations.email_ingest import EmailNormalizer
            NORMALIZERS[provider] = EmailNormalizer()
        elif provider == "grafana":
            from backend.integrations.grafana import GrafanaNormalizer
            NORMALIZERS[provider] = GrafanaNormalizer()
        elif provider == "datadog":
            from backend.integrations.datadog import DatadogNormalizer
            NORMALIZERS[provider] = DatadogNormalizer()

    return NORMALIZERS[provider]  # type: ignore
