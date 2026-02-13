"""Notification dispatcher for incident events.

Sends notifications to configured channels (Slack, Teams, Email, Webhook, PagerDuty)
when incidents are created or escalated. Includes rate limiting to prevent notification spam.
"""

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import (
    ChannelType,
    Incident,
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
)

logger = logging.getLogger(__name__)

# In-memory rate limit cache: (channel_id, incident_id) -> last_sent_at
_rate_limit_cache: dict[tuple[str, str], datetime] = {}

# Severity to color mapping for Slack / Teams messages
SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "warning": "#eab308",
    "low": "#3b82f6",
    "info": "#6b7280",
}

EVENT_LABELS = {
    "incident_created": "New Incident",
    "severity_changed": "Severity Escalated",
    "incident_resolved": "Incident Resolved",
}

# PagerDuty severity mapping (Solace → PagerDuty)
PD_SEVERITY_MAP = {
    "critical": "critical",
    "high": "error",
    "warning": "warning",
    "low": "info",
    "info": "info",
}


def matches_filters(channel: NotificationChannel, incident: Incident) -> bool:
    """Check if incident matches channel's severity/service filters."""
    filters = channel.filters or {}

    # Severity filter
    severities = filters.get("severity")
    if severities and isinstance(severities, list) and len(severities) > 0:
        if incident.severity.value not in severities:
            return False

    # Service filter — check if any alert in the incident matches
    services = filters.get("service")
    if services and isinstance(services, list) and len(services) > 0:
        # Check incident alerts for matching service
        incident_services = {a.service for a in incident.alerts if a.service}
        if not incident_services.intersection(set(services)):
            return False

    return True


def check_rate_limit(channel_id: str, incident_id: str) -> bool:
    """Return True if notification should be sent (not rate-limited)."""
    settings = get_settings()
    cooldown = timedelta(seconds=settings.notification_cooldown_seconds)
    key = (str(channel_id), str(incident_id))
    now = datetime.now(UTC)

    last_sent = _rate_limit_cache.get(key)
    if last_sent and (now - last_sent) < cooldown:
        return False

    _rate_limit_cache[key] = now
    return True


# ──────────────────────────────────────────────────────────────
# Slack
# ──────────────────────────────────────────────────────────────


def format_slack_message(incident: Incident, event_type: str) -> dict:
    """Build a Slack Block Kit message for an incident notification."""
    settings = get_settings()
    severity = incident.severity.value
    color = SEVERITY_COLORS.get(severity, "#6b7280")
    event_label = EVENT_LABELS.get(event_type, event_type)
    alert_count = len(incident.alerts) if incident.alerts else 0
    dashboard_url = f"{settings.solace_dashboard_url}"

    # Get services from alerts
    services = {a.service for a in incident.alerts if a.service} if incident.alerts else set()
    service_text = ", ".join(sorted(services)) if services else "unknown"

    return {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{event_label}*\n*{incident.title}*",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Severity:* {severity.upper()}"},
                            {"type": "mrkdwn", "text": f"*Alerts:* {alert_count}"},
                            {"type": "mrkdwn", "text": f"*Service:* {service_text}"},
                            {"type": "mrkdwn", "text": f"*Status:* {incident.status.value}"},
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"<{dashboard_url}|View in Solace>",
                            },
                        ],
                    },
                ],
            }
        ]
    }


async def _send_slack(channel: NotificationChannel, incident: Incident, event_type: str) -> None:
    """Send a Slack webhook notification."""
    webhook_url = channel.config.get("webhook_url")
    if not webhook_url:
        raise ValueError("Slack channel missing webhook_url in config")

    message = format_slack_message(incident, event_type)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=message)
        response.raise_for_status()


# ──────────────────────────────────────────────────────────────
# Microsoft Teams (Incoming Webhook via Adaptive Cards)
# ──────────────────────────────────────────────────────────────


def format_teams_message(incident: Incident, event_type: str) -> dict:
    """Build a Microsoft Teams Adaptive Card message for an incident."""
    settings = get_settings()
    severity = incident.severity.value
    event_label = EVENT_LABELS.get(event_type, event_type)
    alert_count = len(incident.alerts) if incident.alerts else 0
    dashboard_url = f"{settings.solace_dashboard_url}"

    services = {a.service for a in incident.alerts if a.service} if incident.alerts else set()
    service_text = ", ".join(sorted(services)) if services else "unknown"

    # Teams Workflows / Power Automate webhook format (Adaptive Card)
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "emphasis",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"🔔 {event_label}",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                },
                            ],
                        },
                        {
                            "type": "Container",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": incident.title,
                                    "weight": "Bolder",
                                    "size": "Large",
                                    "wrap": True,
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {"title": "Severity", "value": severity.upper()},
                                        {"title": "Status", "value": incident.status.value.upper()},
                                        {"title": "Alerts", "value": str(alert_count)},
                                        {"title": "Service", "value": service_text},
                                    ],
                                },
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "View in Solace",
                            "url": dashboard_url,
                        }
                    ],
                },
            }
        ],
    }


async def _send_teams(channel: NotificationChannel, incident: Incident, event_type: str) -> None:
    """Send a Microsoft Teams webhook notification."""
    webhook_url = channel.config.get("webhook_url")
    if not webhook_url:
        raise ValueError("Teams channel missing webhook_url in config")

    message = format_teams_message(incident, event_type)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=message)
        response.raise_for_status()


# ──────────────────────────────────────────────────────────────
# Generic Outbound Webhook
# ──────────────────────────────────────────────────────────────


def format_webhook_payload(incident: Incident, event_type: str) -> dict:
    """Build a generic JSON payload for outbound webhooks."""
    settings = get_settings()
    alert_count = len(incident.alerts) if incident.alerts else 0
    services = {a.service for a in incident.alerts if a.service} if incident.alerts else set()

    alerts_data = []
    if incident.alerts:
        for a in incident.alerts[:20]:
            alerts_data.append({
                "id": str(a.id),
                "name": a.name,
                "status": a.status.value,
                "severity": a.severity.value,
                "service": a.service,
                "host": a.host,
                "description": a.description,
                "duplicate_count": a.duplicate_count,
                "starts_at": a.starts_at.isoformat() if a.starts_at else None,
            })

    return {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "solace",
        "dashboard_url": settings.solace_dashboard_url,
        "incident": {
            "id": str(incident.id),
            "title": incident.title,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "acknowledged_at": (
                incident.acknowledged_at.isoformat()
                if incident.acknowledged_at
                else None
            ),
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "alert_count": alert_count,
            "services": sorted(services),
            "alerts": alerts_data,
        },
    }


async def _send_webhook(channel: NotificationChannel, incident: Incident, event_type: str) -> None:
    """Send a generic outbound webhook notification."""
    webhook_url = channel.config.get("webhook_url")
    if not webhook_url:
        raise ValueError("Webhook channel missing webhook_url in config")

    payload = format_webhook_payload(incident, event_type)

    headers = {"Content-Type": "application/json", "User-Agent": "Solace/1.0"}

    # Support optional custom headers
    custom_headers = channel.config.get("headers")
    if custom_headers and isinstance(custom_headers, dict):
        headers.update(custom_headers)

    # Support optional secret for HMAC or bearer auth
    secret = channel.config.get("secret")
    if secret:
        headers["X-Solace-Secret"] = secret

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()


# ──────────────────────────────────────────────────────────────
# PagerDuty (Events API v2)
# ──────────────────────────────────────────────────────────────


def format_pagerduty_event(
    incident: Incident, event_type: str, routing_key: str
) -> dict:
    """Build a PagerDuty Events API v2 payload."""
    settings = get_settings()
    severity = incident.severity.value
    pd_severity = PD_SEVERITY_MAP.get(severity, "info")
    alert_count = len(incident.alerts) if incident.alerts else 0
    services = {a.service for a in incident.alerts if a.service} if incident.alerts else set()
    service_text = ", ".join(sorted(services)) if services else "unknown"

    # Map Solace event types to PagerDuty actions
    if event_type == "incident_resolved":
        action = "resolve"
    elif event_type in ("incident_created", "severity_changed"):
        action = "trigger"
    else:
        action = "trigger"

    payload = {
        "routing_key": routing_key,
        "event_action": action,
        "dedup_key": f"solace-incident-{incident.id}",
    }

    if action == "trigger":
        payload["payload"] = {
            "summary": f"[{severity.upper()}] {incident.title} ({alert_count} alerts)",
            "source": service_text,
            "severity": pd_severity,
            "timestamp": datetime.now(UTC).isoformat(),
            "component": service_text,
            "group": service_text,
            "class": event_type,
            "custom_details": {
                "incident_id": str(incident.id),
                "status": incident.status.value,
                "alert_count": alert_count,
                "services": sorted(services),
                "dashboard_url": settings.solace_dashboard_url,
            },
        }
        payload["links"] = [
            {
                "href": settings.solace_dashboard_url,
                "text": "View in Solace",
            }
        ]

    return payload


async def _send_pagerduty(
    channel: NotificationChannel, incident: Incident, event_type: str
) -> None:
    """Send a PagerDuty Events API v2 notification."""
    routing_key = channel.config.get("routing_key")
    if not routing_key:
        raise ValueError("PagerDuty channel missing routing_key in config")

    payload = format_pagerduty_event(incident, event_type, routing_key)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
        )
        response.raise_for_status()


# ──────────────────────────────────────────────────────────────
# Email
# ──────────────────────────────────────────────────────────────


def format_email_html(incident: Incident, event_type: str) -> tuple[str, str]:
    """Build an HTML email for an incident notification. Returns (subject, html_body)."""
    severity = incident.severity.value.upper()
    event_label = EVENT_LABELS.get(event_type, event_type)
    alert_count = len(incident.alerts) if incident.alerts else 0
    settings = get_settings()

    subject = f"[Solace] [{severity}] {event_label}: {incident.title}"

    # Build alert rows
    td = "padding:6px 12px;border-bottom:1px solid #1e2736"
    alert_rows = ""
    if incident.alerts:
        for alert in incident.alerts[:10]:  # Limit to 10 alerts
            svc = alert.service or "-"
            alert_rows += (
                f'<tr><td style="{td}">{alert.name}</td>'
                f'<td style="{td}">{alert.severity.value}</td>'
                f'<td style="{td}">{alert.status.value}</td>'
                f'<td style="{td}">{svc}</td></tr>'
            )

    wrap = (
        "font-family:sans-serif;max-width:600px;"
        "margin:0 auto;background:#0a0e14;color:#c5cdd8;"
        "padding:24px;border-radius:8px"
    )
    html = f"""
    <div style="{wrap}">
        <h2 style="color:#e8ecf1;margin-top:0;">{event_label}</h2>
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr>
                <td style="padding:8px 0;color:#3d4f65;">Incident</td>
                <td style="padding:8px 0;color:#e8ecf1;font-weight:600;">{incident.title}</td>
            </tr>
            <tr>
                <td style="padding:8px 0;color:#3d4f65;">Severity</td>
                <td style="padding:8px 0;color:#e8ecf1;font-weight:600;">{severity}</td>
            </tr>
            <tr>
                <td style="padding:8px 0;color:#3d4f65;">Alert Count</td>
                <td style="padding:8px 0;color:#e8ecf1;">{alert_count}</td>
            </tr>
            <tr>
                <td style="padding:8px 0;color:#3d4f65;">Status</td>
                <td style="padding:8px 0;color:#e8ecf1;">{incident.status.value}</td>
            </tr>
        </table>

        {f'''<h3 style="color:#e8ecf1;margin-top:24px;">Correlated Alerts</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr style="background:#111720;">
                <th style="padding:8px 12px;text-align:left;color:#3d4f65;">Name</th>
                <th style="padding:8px 12px;text-align:left;color:#3d4f65;">Severity</th>
                <th style="padding:8px 12px;text-align:left;color:#3d4f65;">Status</th>
                <th style="padding:8px 12px;text-align:left;color:#3d4f65;">Service</th>
            </tr>
            {alert_rows}
        </table>''' if alert_rows else ''}

        <p style="margin-top:24px;">
            <a href="{settings.solace_dashboard_url}" style="color:#10b981;">View in Solace</a>
        </p>
    </div>
    """

    return subject, html


async def _send_email(channel: NotificationChannel, incident: Incident, event_type: str) -> None:
    """Send an email notification via SMTP."""
    settings = get_settings()
    if not settings.smtp_host:
        raise ValueError("SMTP not configured (SMTP_HOST not set)")

    recipients = channel.config.get("recipients", [])
    if not recipients:
        raise ValueError("Email channel missing recipients in config")

    from_address = channel.config.get("from_address", settings.smtp_from_address)
    subject, html_body = format_email_html(incident, event_type)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    # Send via SMTP (synchronous — acceptable for now, move to background later)
    if settings.smtp_use_tls:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

    try:
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(from_address, recipients, msg.as_string())
    finally:
        server.quit()


# ──────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────

# Map channel types to sender functions
_SENDERS = {
    ChannelType.SLACK: _send_slack,
    ChannelType.EMAIL: _send_email,
    ChannelType.TEAMS: _send_teams,
    ChannelType.WEBHOOK: _send_webhook,
    ChannelType.PAGERDUTY: _send_pagerduty,
}


async def dispatch_notifications(
    db: AsyncSession,
    incident: Incident,
    event_type: str,
) -> None:
    """Send notifications to all matching active channels.

    This is called after correlation creates/updates incidents.
    """
    # Query active channels
    stmt = select(NotificationChannel).where(
        NotificationChannel.is_active.is_(True)
    )
    result = await db.execute(stmt)
    channels = result.scalars().all()

    if not channels:
        return

    for channel in channels:
        # Check filters
        if not matches_filters(channel, incident):
            continue

        # Check rate limit
        if not check_rate_limit(str(channel.id), str(incident.id)):
            logger.debug(
                f"Notification rate-limited: channel={channel.name}, incident={incident.title}"
            )
            continue

        # Create log entry
        log = NotificationLog(
            channel_id=channel.id,
            incident_id=incident.id,
            event_type=event_type,
            status=NotificationStatus.PENDING,
        )
        db.add(log)

        try:
            sender = _SENDERS.get(channel.channel_type)
            if sender:
                await sender(channel, incident, event_type)
            else:
                raise ValueError(f"Unknown channel type: {channel.channel_type}")

            log.status = NotificationStatus.SENT
            log.sent_at = datetime.now(UTC)
            logger.info(
                f"Notification sent: channel={channel.name}, "
                f"incident={incident.title}, event={event_type}"
            )
        except Exception as e:
            log.status = NotificationStatus.FAILED
            log.error_message = str(e)[:500]
            logger.warning(
                f"Notification failed: channel={channel.name}, "
                f"incident={incident.title}, error={e}"
            )

        await db.flush()
