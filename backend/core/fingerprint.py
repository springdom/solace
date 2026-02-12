import hashlib
import json


def generate_fingerprint(
    source: str,
    name: str,
    service: str | None = None,
    host: str | None = None,
    severity: str | None = None,
    labels: dict | None = None,
) -> str:
    """Generate a deterministic fingerprint for an alert.

    The fingerprint is used to identify duplicate alerts. Two alerts with
    the same fingerprint are considered duplicates of the same underlying issue.

    Identity fields (included in fingerprint):
        - source: Where the alert came from
        - name: Alert name/rule
        - service: Affected service
        - host: Affected host/instance

    Excluded from fingerprint (volatile fields):
        - severity (can change for the same issue)
        - description (may vary between occurrences)
        - timestamp
        - metric values
        - annotations

    Labels are optionally included — only "identity labels" that distinguish
    genuinely different alerts should contribute. By default, all labels
    are included. In the future, this can be made configurable per-integration.
    """
    identity = {
        "source": source or "",
        "name": name,
        "service": service or "",
        "host": host or "",
    }

    # Include labels if provided (sorted for determinism)
    if labels:
        # Filter out volatile/noisy labels
        volatile_keys = {"timestamp", "value", "description", "summary", "generatorURL"}
        filtered = {k: v for k, v in sorted(labels.items()) if k not in volatile_keys}
        if filtered:
            identity["labels"] = filtered

    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
