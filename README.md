<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status: Alpha" />
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License: Apache 2.0" />
</p>

# Solace

Open-source alert management and incident response platform. Ingest alerts from any monitoring source, deduplicate them, auto-correlate into incidents, and manage the response — all from a single dashboard.

**Think PagerDuty / OpsGenie, but open-source and self-hosted.**

## Features

### Authentication & Access Control
- **JWT-based authentication** — Secure login with username/password, 8-hour token expiry
- **Role-based access control (RBAC)** — Three roles: Admin (full access), User (read + acknowledge/resolve), Viewer (read-only)
- **Default admin account** — Auto-seeded on first startup with configurable credentials
- **First-login password change** — Admin account requires password change on first login
- **API key backward compatibility** — Webhook ingestion continues to use `X-API-Key` header, existing integrations unaffected
- **User management** — Admin panel to create, edit, and deactivate user accounts

### On-Call Scheduling
- **Flexible rotations** — Hourly, daily, weekly, or custom rotation intervals
- **Member management** — Add team members to schedules with ordered rotation positions
- **Timezone-aware handoffs** — Configure handoff time and timezone per schedule
- **Temporary overrides** — Swap on-call duty for a time range with reason tracking
- **"Who's On Call" view** — Real-time display of the current on-call person per schedule

### Escalation Policies
- **Multi-level escalation** — Define escalation levels with configurable timeouts (1-1440 minutes)
- **Mixed targets** — Each level can notify users directly or the current on-call from a schedule
- **Repeat support** — Policies can repeat through all levels N times before stopping
- **Service-to-policy mapping** — Map services to escalation policies using glob patterns (e.g., `billing-*`, `*`)
- **Priority ordering** — When multiple mappings match, the lowest priority number wins
- **Severity filtering** — Optionally restrict mappings to specific severity levels

### Alert Ingestion & Normalization
- **6 built-in webhook normalizers** — Generic, Prometheus Alertmanager, Grafana, Splunk, Datadog, and Email ingest
- **Pluggable architecture** — Each provider has its own normalizer that maps vendor-specific payloads to Solace's internal format
- **Auto-severity mapping** — Provider-specific priority/severity levels are normalized to Solace's 5-level model (critical, high, warning, low, info)

### Deduplication
- **Fingerprint-based dedup** — SHA256 hash of identity fields (source, name, service, host, labels) ensures identical alerts merge rather than duplicate
- **Configurable dedup window** — Default 5 minutes; identical alerts within the window increment `duplicate_count`
- **Occurrence timeline** — Every duplicate arrival is tracked with a timestamp for frequency analysis

### Incident Correlation
- **Automatic service-based grouping** — Alerts from the same service within a configurable time window (default 10 min) are grouped into a single incident
- **Severity auto-promotion** — Incident severity always reflects the worst alert severity
- **Auto-resolve** — When all alerts in an incident resolve, the incident auto-resolves

### Alert Lifecycle
- **Full status workflow** — Firing → Acknowledged → Resolved, plus Suppressed and Archived states
- **Acknowledge & resolve** — One-click actions from the dashboard or via API
- **Bulk operations** — Select multiple alerts and acknowledge or resolve them in one action
- **Archive** — Archive resolved alerts older than N days to keep the dashboard clean

### Incident Management
- **Incident timeline** — Every action (created, alert added, severity changed, acknowledged, resolved) is recorded as a timestamped event
- **Incident detail view** — See all correlated alerts, event audit trail, and incident metadata in one place
- **Cascade actions** — Acknowledging/resolving an incident applies to all its alerts

### Notification Channels (5 types)
- **Slack** — Block Kit formatted messages with severity color coding, alert counts, service info, and dashboard links
- **Microsoft Teams** — Adaptive Card messages via incoming webhook or Power Automate workflow URLs
- **Email** — HTML-formatted incident notifications via SMTP with correlated alert tables
- **Generic Webhook (Outbound)** — JSON payload with full incident and alert data, optional shared secret for HMAC verification, custom headers support
- **PagerDuty** — Events API v2 integration; triggers, resolves, and dedup keys sync incidents to PagerDuty services
- **Per-channel filters** — Filter notifications by severity and/or service
- **Rate limiting** — Per-channel, per-incident cooldown prevents notification spam
- **Delivery logs** — Every notification attempt is logged with status (pending/sent/failed) and error details
- **Test button** — Send a test notification through any channel from the UI

### Silence / Maintenance Windows
- **Time-based suppression** — Define start/end times for maintenance windows
- **Flexible matchers** — Match by service (list), severity (list), or label key-value pairs
- **AND logic** — All matchers must match for an alert to be suppressed
- **CRUD management** — Create, edit, and view active/expired windows from the UI

### Alert Enrichment
- **Tags** — Free-form string tags with add/remove from UI or API; stored as JSONB with GIN index for fast queries
- **Investigation notes** — Timestamped notes with author attribution and full CRUD
- **External ticket linking** — Link alerts to Jira, GitHub, or any URL; auto-prepends `https://` if missing
- **Runbook URL** — Each alert can carry a runbook link from the source system
- **Raw payload** — Full original webhook payload preserved for forensic inspection

### Dashboard & UI
- **Light and dark themes** — Toggle between a high-contrast dark ops-console theme and a clean light theme; preference persisted in localStorage
- **Real-time updates** — WebSocket connection with automatic reconnect and fallback polling
- **Keyboard shortcuts** — `j`/`k` navigation, `a` acknowledge, `r` resolve, `Esc` close, `?` help
- **Search & filter** — Full-text search across name, service, host, tags with status/severity/service filters
- **Sortable columns** — Sort by time, severity, name, service, duplicate count, or status
- **Pagination** — Configurable page size with server-side pagination
- **Stats bar** — Live counts of alerts by status/severity, incident counts, MTTA, and MTTR

### API & Integration
- **Full REST API** — Every feature is accessible via API (alerts, incidents, silences, notifications, on-call, stats, settings)
- **OpenAPI docs** — Auto-generated Swagger UI at `/docs`
- **Health checks** — Liveness (`/health`) and readiness (`/health/ready`) endpoints for Kubernetes probes
- **WebSocket events** — Real-time event stream for `alert.created`, `incident.updated`, `incident_created`, `severity_changed`, `incident_resolved`
- **Dual auth** — JWT Bearer tokens for user sessions, `X-API-Key` header for webhook ingestion and external integrations

## Architecture

```
Prometheus ──┐
Grafana ─────┤                   ┌─────────────┐     ┌────────────┐
Datadog ─────┼─▶ Webhook API ──▶ │ Normalizer  │ ──▶ │  Dedup     │
Splunk ──────┤   (X-API-Key)     │ (pluggable) │     │  Engine    │
Email ───────┤                   └─────────────┘     └─────┬──────┘
Custom ──────┘                                             │
                                                     ┌─────▼──────┐
                                                     │ Silence     │
                                                     │ Check       │
                                                     └─────┬──────┘
                                                           │
                                                     ┌─────▼──────┐     ┌──────────────┐
                                                     │ Correlation │──▶  │ Notifications │
                                                     │ Engine      │     └──────┬───────┘
                                                     └─────┬──────┘            │
                                                           │            ┌──────▼───────┐
                                                           │            │  Escalation   │
                                                           │            │  Engine       │
                                                           │            └──────┬───────┘
                                                           │                   │
                                              ┌────────────▼───────────────────▼┐
                                              │  PostgreSQL + Redis              │
                                              └────────────┬────────────────────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │  React Dashboard (WS)   │
                                              │  JWT Auth + RBAC        │
                                              │  (Vite + Tailwind)      │
                                              └─────────────────────────┘
```

## Quick Start

### Docker Compose (recommended)

```bash
git clone https://github.com/springdom/solace.git
cd solace
docker compose up --build
```

- **Dashboard:** http://localhost:3000
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

**Default login:** `admin` / `admin` (you'll be prompted to change the password on first login)

### Send a test alert

```bash
# Generic webhook
curl -X POST http://localhost:8000/api/v1/webhooks/generic \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HighCPU",
    "severity": "critical",
    "service": "payment-api",
    "host": "web-01",
    "description": "CPU usage above 95% for 10 minutes",
    "tags": ["production", "us-east-1"]
  }'

# Prometheus Alertmanager
curl -X POST http://localhost:8000/api/v1/webhooks/prometheus \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "DiskFull",
        "instance": "db-01:9090",
        "job": "postgres",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Disk 95% full on db-01"
      },
      "startsAt": "2024-01-15T10:00:00.000Z",
      "endsAt": "0001-01-01T00:00:00Z"
    }]
  }'

# Grafana unified alerting
curl -X POST http://localhost:8000/api/v1/webhooks/grafana \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": { "alertname": "HighMemory", "grafana_folder": "Infrastructure" },
      "annotations": { "summary": "Memory above 90%", "severity": "high" },
      "startsAt": "2024-01-15T10:00:00.000Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "values": { "B": 92.5 }
    }]
  }'

# Datadog monitor webhook
curl -X POST http://localhost:8000/api/v1/webhooks/datadog \
  -H "Content-Type: application/json" \
  -d '{
    "id": "123456789",
    "title": "CPU is high on web-01",
    "text": "CPU utilization above threshold",
    "alert_status": "triggered",
    "priority": "P1",
    "hostname": "web-01",
    "org": { "name": "MyOrg" },
    "tags": "env:production,service:payment-api"
  }'

# Splunk webhook alert
curl -X POST http://localhost:8000/api/v1/webhooks/splunk \
  -H "Content-Type: application/json" \
  -d '{
    "result": {
      "host": "web-01",
      "severity": "critical",
      "service": "payment-api",
      "message": "CPU usage above 95% for 10 minutes"
    },
    "sid": "scheduler_admin_HighCPU_at_17000000_132",
    "search_name": "High CPU Usage Alert"
  }'
```

### Test incident correlation

Alerts from the same service auto-group into a single incident:

```bash
# These two alerts will be correlated into ONE incident
curl -X POST http://localhost:8000/api/v1/webhooks/generic \
  -H "Content-Type: application/json" \
  -d '{"name":"HighCPU","severity":"critical","service":"payment-api","host":"web-01"}'

curl -X POST http://localhost:8000/api/v1/webhooks/generic \
  -H "Content-Type: application/json" \
  -d '{"name":"HighMemory","severity":"high","service":"payment-api","host":"web-02"}'

# This creates a SEPARATE incident (different service)
curl -X POST http://localhost:8000/api/v1/webhooks/generic \
  -H "Content-Type: application/json" \
  -d '{"name":"HighErrorRate","severity":"warning","service":"auth-service"}'
```

### Configure notification channels

```bash
# Slack
curl -X POST http://localhost:8000/api/v1/notifications/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ops Slack",
    "channel_type": "slack",
    "config": { "webhook_url": "https://hooks.slack.com/services/YOUR/HOOK/URL" },
    "filters": { "severity": ["critical", "high"] }
  }'

# Microsoft Teams
curl -X POST http://localhost:8000/api/v1/notifications/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DevOps Teams",
    "channel_type": "teams",
    "config": { "webhook_url": "https://your-org.webhook.office.com/..." },
    "filters": { "severity": ["critical"] }
  }'

# PagerDuty
curl -X POST http://localhost:8000/api/v1/notifications/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PagerDuty On-Call",
    "channel_type": "pagerduty",
    "config": { "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY" },
    "filters": { "severity": ["critical"] }
  }'

# Generic outbound webhook
curl -X POST http://localhost:8000/api/v1/notifications/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Automation Webhook",
    "channel_type": "webhook",
    "config": {
      "webhook_url": "https://your-service.com/hooks/solace",
      "secret": "optional-shared-secret",
      "headers": { "X-Custom-Header": "value" }
    }
  }'
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Login with username/password, returns JWT |
| `GET` | `/api/v1/auth/me` | Get current user profile |
| `POST` | `/api/v1/auth/change-password` | Change password |

### Users (Admin only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/users` | List users |
| `POST` | `/api/v1/users` | Create user |
| `PUT` | `/api/v1/users/{id}` | Update user profile/role |
| `POST` | `/api/v1/users/{id}/reset-password` | Reset user password |
| `DELETE` | `/api/v1/users/{id}` | Deactivate user |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (DB + Redis) |

### Webhooks (Alert Ingestion)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/webhooks/generic` | Generic webhook |
| `POST` | `/api/v1/webhooks/prometheus` | Prometheus Alertmanager |
| `POST` | `/api/v1/webhooks/grafana` | Grafana unified alerting |
| `POST` | `/api/v1/webhooks/datadog` | Datadog monitor webhook |
| `POST` | `/api/v1/webhooks/splunk` | Splunk saved search webhook |
| `POST` | `/api/v1/webhooks/email_ingest` | Email-based alert ingestion |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/alerts` | List alerts (filterable, sortable, paginated) |
| `GET` | `/api/v1/alerts/{id}` | Get alert by ID |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| `POST` | `/api/v1/alerts/{id}/resolve` | Resolve alert |
| `PUT` | `/api/v1/alerts/{id}/tags` | Replace all tags |
| `POST` | `/api/v1/alerts/{id}/tags/{tag}` | Add a single tag |
| `DELETE` | `/api/v1/alerts/{id}/tags/{tag}` | Remove a tag |
| `GET` | `/api/v1/alerts/{id}/notes` | List investigation notes |
| `POST` | `/api/v1/alerts/{id}/notes` | Add a note |
| `PUT` | `/api/v1/alerts/notes/{id}` | Edit a note |
| `DELETE` | `/api/v1/alerts/notes/{id}` | Delete a note |
| `GET` | `/api/v1/alerts/{id}/history` | Get occurrence timeline |
| `PUT` | `/api/v1/alerts/{id}/ticket` | Set external ticket URL |
| `POST` | `/api/v1/alerts/bulk/acknowledge` | Bulk acknowledge |
| `POST` | `/api/v1/alerts/bulk/resolve` | Bulk resolve |
| `POST` | `/api/v1/alerts/archive` | Archive old resolved alerts |

### Incidents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/incidents` | List incidents (filterable, sortable, paginated) |
| `GET` | `/api/v1/incidents/{id}` | Get incident with alerts + event timeline |
| `POST` | `/api/v1/incidents/{id}/acknowledge` | Acknowledge incident + all alerts |
| `POST` | `/api/v1/incidents/{id}/resolve` | Resolve incident + all alerts |

### Silences (Maintenance Windows)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/silences` | List silence windows (filterable by state) |
| `POST` | `/api/v1/silences` | Create silence window |
| `GET` | `/api/v1/silences/{id}` | Get silence window |
| `PUT` | `/api/v1/silences/{id}` | Update silence window |
| `DELETE` | `/api/v1/silences/{id}` | Delete silence window |

### Notification Channels
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/notifications/channels` | List all channels |
| `POST` | `/api/v1/notifications/channels` | Create channel (slack/teams/email/webhook/pagerduty) |
| `GET` | `/api/v1/notifications/channels/{id}` | Get channel |
| `PUT` | `/api/v1/notifications/channels/{id}` | Update channel |
| `DELETE` | `/api/v1/notifications/channels/{id}` | Delete channel |
| `POST` | `/api/v1/notifications/channels/{id}/test` | Send test notification |
| `GET` | `/api/v1/notifications/logs` | List delivery logs |

### On-Call Schedules
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/oncall/schedules` | List schedules (paginated, `active_only` filter) |
| `POST` | `/api/v1/oncall/schedules` | Create schedule (admin) |
| `GET` | `/api/v1/oncall/schedules/{id}` | Get schedule |
| `PUT` | `/api/v1/oncall/schedules/{id}` | Update schedule (admin) |
| `DELETE` | `/api/v1/oncall/schedules/{id}` | Delete schedule (admin) |
| `GET` | `/api/v1/oncall/schedules/{id}/current` | Get who is currently on call |
| `POST` | `/api/v1/oncall/schedules/{id}/overrides` | Create temporary override (admin) |
| `DELETE` | `/api/v1/oncall/overrides/{id}` | Delete override (admin) |

### Escalation Policies
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/oncall/policies` | List escalation policies |
| `POST` | `/api/v1/oncall/policies` | Create policy (admin) |
| `GET` | `/api/v1/oncall/policies/{id}` | Get policy |
| `PUT` | `/api/v1/oncall/policies/{id}` | Update policy (admin) |
| `DELETE` | `/api/v1/oncall/policies/{id}` | Delete policy (admin) |

### Service Mappings
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/oncall/mappings` | List service-to-policy mappings |
| `POST` | `/api/v1/oncall/mappings` | Create mapping (admin) |
| `DELETE` | `/api/v1/oncall/mappings/{id}` | Delete mapping (admin) |

### Stats & Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/stats` | Dashboard statistics (counts, MTTA, MTTR) |
| `GET` | `/api/v1/settings` | Application configuration |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ws?token={jwt_or_api_key}` | Real-time event stream |

## Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://solace:solace@localhost:5432/solace` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `API_KEY` | `""` | API key for webhook ingestion (empty = no auth in dev) |
| `SECRET_KEY` | `change-me-to-a-random-secret-key` | Secret for JWT signing |
| `ADMIN_USERNAME` | `admin` | Default admin username (created on first startup) |
| `ADMIN_PASSWORD` | `admin` | Default admin password |
| `ADMIN_EMAIL` | `admin@solace.local` | Default admin email |
| `JWT_EXPIRE_MINUTES` | `480` | JWT token expiry (8 hours) |
| `DEDUP_WINDOW_SECONDS` | `300` | Window for deduplicating identical alerts (5 min) |
| `CORRELATION_WINDOW_SECONDS` | `600` | Window for correlating alerts into incidents (10 min) |
| `NOTIFICATION_COOLDOWN_SECONDS` | `300` | Per-channel, per-incident notification cooldown (5 min) |
| `SOLACE_DASHBOARD_URL` | `http://localhost:3000` | Dashboard URL (used in notification links) |
| `APP_ENV` | `development` | Environment (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SMTP_HOST` | `""` | SMTP server for email notifications |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | `""` | SMTP username |
| `SMTP_PASSWORD` | `""` | SMTP password |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SMTP_FROM_ADDRESS` | `solace@localhost` | Sender address for email notifications |

## Tech Stack

**Backend:** Python 3.12+, FastAPI, async SQLAlchemy (asyncpg), Alembic, PostgreSQL, Redis, python-jose (JWT), passlib (bcrypt)

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand

**Deployment:** Docker Compose, Kubernetes-ready health probes

## Development

### Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Lint

```bash
ruff check backend/
```

### Local development (without Docker)

```bash
# Start PostgreSQL and Redis
# Create database: CREATE DATABASE solace;

# Run migrations
alembic upgrade head

# Start API server
uvicorn backend.main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Roadmap

### Completed
- [x] Multi-source webhook ingestion (Generic, Prometheus, Grafana, Datadog, Splunk, Email)
- [x] Fingerprint-based deduplication with configurable window
- [x] Service-based automatic incident correlation
- [x] Full alert lifecycle (firing, acknowledged, resolved, suppressed, archived)
- [x] Incident management with event audit trail
- [x] Notification channels: Slack, Microsoft Teams, Email, Webhook (outbound), PagerDuty
- [x] Notification filters, rate limiting, delivery logs, and test button
- [x] Silence / maintenance windows with flexible matchers
- [x] Alert tagging and investigation notes
- [x] External ticket URL linking (Jira, GitHub, etc.)
- [x] Runbook URL support
- [x] Bulk acknowledge/resolve operations
- [x] Archive old resolved alerts
- [x] Dashboard stats (MTTA, MTTR, counts by status/severity)
- [x] Real-time WebSocket updates with fallback polling
- [x] Keyboard shortcuts for fast navigation
- [x] Light and dark theme toggle
- [x] JWT authentication with default admin account
- [x] Role-based access control (admin, user, viewer)
- [x] User management (create, edit, deactivate)
- [x] On-call scheduling (hourly/daily/weekly/custom rotations)
- [x] Temporary on-call overrides
- [x] Escalation policies with multi-level targets
- [x] Service-to-policy mapping with glob patterns and priority ordering

### Next Up
- [ ] SSO integration (Google, GitHub, SAML)
- [ ] SMS and voice call notifications (Twilio)
- [ ] Background escalation checker (auto-escalate if not ack'd in N minutes)
- [ ] Analytics and reporting dashboards
- [ ] Status pages (public incident status)
- [ ] Heartbeat / dead-man monitoring
- [ ] Post-incident review and retrospectives
- [ ] Topology-aware correlation (service dependency graph)
- [ ] Alert auto-expire / timeout

## License

Apache 2.0
