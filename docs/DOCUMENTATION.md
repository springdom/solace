# Solace — Alert Management Platform

**Internal Documentation**
Last updated: February 2026

---

## What is Solace?

Solace is a self-hosted alert management platform that ingests alerts from monitoring tools (Prometheus, Grafana, Datadog, Splunk, and more), deduplicates them, automatically groups related alerts into incidents, and provides a single dashboard to manage the response — complete with user authentication, on-call scheduling, and escalation policies.

Think of it as a lightweight, open-source alternative to PagerDuty or Opsgenie that we control entirely.

### Why Solace?

Currently, Splunk alert emails land in a shared inbox. When multiple alerts fire for the same issue (e.g., 10 hosts throwing the same Java exception), each one is a separate email. There's no grouping, no dedup, and no easy way to know "is this the same issue someone is already working on?"

Solace fixes this by automatically correlating alerts from the same service into a single incident and tracking the response lifecycle (open → acknowledged → resolved).

---

## Architecture Overview

```
Prometheus ──┐
Grafana ─────┤
Datadog ─────┼──▶ Webhook API ──▶ Normalizer ──▶ Dedup ──▶ Runbook ──▶ Silence ──▶ Correlation
Splunk ──────┤    (X-API-Key)     (pluggable)                              │
Email ───────┘                                                       Escalation
                                                                      Engine
                    JWT Auth ◀── React Dashboard ──▶ On-Call UI            │
                       │              │                                    │
                       ▼              ▼                                    ▼
                    Users        PostgreSQL + Redis              Notifications
```

**Components:**

- **FastAPI backend** — Python 3.12 async API server. Handles webhook ingestion, alert/incident CRUD, authentication, on-call scheduling, escalation, and the REST API.
- **PostgreSQL 16** — Stores alerts, incidents, users, on-call schedules, escalation policies, and timeline events. Schema managed by Alembic migrations.
- **Redis 7** — Used for caching, notification cooldown tracking, and settings overrides.
- **React frontend** — Single-page dashboard built with Vite + TypeScript + Tailwind CSS. Light/dark theme toggle, JWT auth, real-time WebSocket updates, on-call management UI.

All components run as Docker containers via `docker compose`.

---

## Deployment

### Prerequisites

- Docker and Docker Compose
- Git access to the repository

### Installation

```bash
git clone https://github.com/springdom/solace.git
cd solace
docker compose up --build -d
```

This starts four containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `solace-api` | 8000 | FastAPI backend |
| `solace-frontend` | 3000 | React dashboard |
| `solace-db` | 5432 | PostgreSQL 16 |
| `solace-redis` | 6379 | Redis 7 |

### Accessing

- **Dashboard:** http://localhost:3000 (login: `admin` / `admin`)
- **API documentation (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

On first login, you'll be prompted to change the default admin password.

### Updating

```bash
cd solace
git pull
docker compose down
docker compose up --build -d
```

### Configuration

All settings are via environment variables (set in `docker-compose.yml` or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://solace:solace@db:5432/solace` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `API_KEY` | `""` | API key for webhook ingestion (empty = no auth in dev) |
| `SECRET_KEY` | `change-me-to-a-random-secret-key` | Secret for JWT signing |
| `ADMIN_USERNAME` | `admin` | Default admin username (auto-created on first startup) |
| `ADMIN_PASSWORD` | `admin` | Default admin password |
| `ADMIN_EMAIL` | `admin@solace.local` | Default admin email |
| `JWT_EXPIRE_MINUTES` | `480` | JWT token expiry in minutes (8 hours) |
| `DEDUP_WINDOW_SECONDS` | `300` | How long (in seconds) to treat identical alerts as duplicates. Default 5 minutes. |
| `CORRELATION_WINDOW_SECONDS` | `600` | How long (in seconds) to group alerts from the same service into one incident. Default 10 minutes. |
| `NOTIFICATION_COOLDOWN_SECONDS` | `300` | Per-channel, per-incident notification cooldown (5 min) |
| `SOLACE_DASHBOARD_URL` | `http://localhost:3000` | Dashboard URL used in notification links |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Authentication & Access Control

### Overview

Solace uses JWT-based authentication for user sessions and API key authentication for webhook ingestion. A default admin account is automatically created on first startup.

### Roles

| Role | Read | Acknowledge/Resolve | Admin Actions |
|------|------|---------------------|---------------|
| **Admin** | All data | Alerts, incidents | Users, silences, notification channels, on-call, settings |
| **User** | All data | Alerts, incidents | — |
| **Viewer** | All data | — | — |

### Login Flow

1. Navigate to the dashboard — you'll see the login page
2. Enter username and password
3. On first login with the default admin account, you'll be prompted to set a new password
4. JWT token is stored in the browser and used for all subsequent API calls (8-hour expiry)

### API Authentication

**User sessions (JWT):**
```bash
# Login to get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' | jq -r .access_token)

# Use the token for API calls
curl http://localhost:8000/api/v1/alerts \
  -H "Authorization: Bearer $TOKEN"
```

**Webhook ingestion (API key):**
```bash
# Webhooks use X-API-Key header (unchanged from before)
curl -X POST http://localhost:8000/api/v1/webhooks/generic \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name":"TestAlert","severity":"warning","service":"my-svc"}'
```

In development mode (when `API_KEY` is empty), authentication is bypassed for convenience.

### User Management

Admins can manage users from the **Users** tab in the dashboard:

- **Create user** — Set email, username, password, and role
- **Edit user** — Change display name, role, or active status
- **Reset password** — Set a new password for a user (they'll be prompted to change it)
- **Deactivate** — Disable a user account (admins cannot deactivate themselves)

---

## On-Call Scheduling

### Schedules

On-call schedules define who is on call and when. Each schedule has:

- **Rotation type** — Hourly, daily, weekly, or custom
- **Members** — Ordered list of users who rotate through on-call duty
- **Handoff time** — Time of day when rotation handoffs occur (e.g., 09:00)
- **Timezone** — All handoff calculations are timezone-aware
- **Effective from** — When the schedule starts

**Rotation calculation:** The current on-call person is determined by how many rotation intervals have elapsed since `effective_from`, indexed into the members list. For example, with a weekly rotation and 3 members starting Jan 1:
- Jan 1-7: Member 1, Jan 8-14: Member 2, Jan 15-21: Member 3, Jan 22-28: Member 1 (wraps)

### Overrides

Temporary overrides allow swapping who is on call for a specific time range. Overrides take priority over the regular rotation. Common use cases:

- Covering for a teammate who is on vacation
- Swapping shifts for personal scheduling
- Emergency coverage changes

### Escalation Policies

Escalation policies define what happens when an incident occurs for a service:

- **Levels** — Each policy has one or more escalation levels
- **Targets** — Each level notifies one or more targets (individual users or the current on-call from a schedule)
- **Timeout** — If no one acknowledges within the timeout (1-1440 minutes), escalation advances to the next level
- **Repeat** — Policies can repeat through all levels N times

### Service Mappings

Service mappings connect services to escalation policies:

- **Service pattern** — Glob pattern matching (e.g., `billing-*` matches `billing-api`, `billing-worker`)
- **Severity filter** — Optionally only escalate for certain severities (e.g., critical, high)
- **Priority** — When multiple patterns match, the lowest priority number wins (0 = highest priority)

**Example setup:**
1. Create a schedule: "Platform On-Call" with 3 engineers on weekly rotation
2. Create a policy: Level 1 notifies the Platform On-Call schedule (5 min timeout), Level 2 notifies the engineering manager directly
3. Create a mapping: `platform-*` service pattern → Platform Escalation Policy

---

## Connecting Splunk

There are two ways to get Splunk alerts into Solace. Both can be used simultaneously.

### Option A: Splunk Webhook (Recommended)

This is the cleanest approach. Splunk sends alert data directly to Solace when a saved search triggers.

**Step 1 — Add Solace URL to Splunk's webhook allow list**

In Splunk's `server.conf` (or via the Splunk web UI under Settings → Server settings), add the Solace URL to the allowed webhook destinations:

```ini
[alerting]
webhook_allow_list = http://your-solace-host:8000/api/v1/webhooks/splunk
```

**Step 2 — Configure your saved search**

For best results, modify your SPL query to aggregate results before sending. This ensures the webhook payload contains meaningful summary data rather than just a single raw log line.

Example — current email-based query:

```spl
index=*
| rex field=_raw "(?<message>ERROR|FATAL)"
| search message="ERROR" OR message="FATAL"
| table host, source, message, _raw
```

Recommended webhook-optimized version:

```spl
index=*
| rex field=_raw "(?<message>ERROR|FATAL)"
| search message="ERROR" OR message="FATAL"
| stats count as error_count
    latest(_raw) as latest_error
    dc(host) as affected_hosts
    values(host) as hosts
    by source, message
| eval severity=if(message=="FATAL" OR error_count>50, "critical",
    if(error_count>10, "high", "warning"))
| eval service=replace(source, "^.*/([^/]+)/log.*$", "\1")
| eval host=mvindex(hosts, 0)
```

This produces one row per source+error level with a count, affected hosts, and auto-calculated severity.

**Step 3 — Add the webhook action**

1. In Splunk, go to **Settings → Searches, reports, and alerts**
2. Find your saved search → **Edit → Edit actions**
3. Click **Add Actions → Webhook**
4. Set URL to: `http://your-solace-host:8000/api/v1/webhooks/splunk`
5. Click **Save**

You can keep the email action alongside the webhook — both will fire.

**What Solace does with the webhook payload:**

The Splunk normalizer automatically extracts structured data from the result fields:

| Solace Field | Splunk Fields Checked (in order) |
|---|---|
| **Severity** | `severity`, `priority`, `urgency`, `level`, `risk_score`, `risk_level` |
| **Host** | `host`, `hostname`, `src_host`, `dest`, `dest_host`, `dvc`, `server`, `instance` |
| **Service** | `service`, `app`, `application`, `service_name`, `sourcetype` |
| **Description** | `message`, `msg`, `description`, `summary`, `latest_error`, `_raw` |
| **Environment** | `environment`, `env`, `tier`, `stage`, `datacenter`, `region` |

If a short value like "ERROR" is found for description, Solace automatically prefers longer fields like `latest_error` or `_raw` for more context.

Severity values are mapped as follows:

| Splunk Value | Solace Severity |
|---|---|
| `critical`, `crit`, `urgent` | Critical |
| `high`, `major` | High |
| `warning`, `warn`, `medium` | Warning |
| `low`, `minor` | Low |
| `info`, `informational` | Info |
| Numeric `risk_score` ≥ 80 | Critical |
| Numeric `risk_score` ≥ 60 | High |
| Numeric `risk_score` ≥ 40 | Warning |

### Option B: Email Ingestion

If you don't want to change anything in Splunk, you can forward alert emails to Solace. This approach parses the HTML table that Splunk includes in alert emails and creates one alert per result row.

**Endpoint:** `POST /api/v1/webhooks/email`

**Payload format:**

```json
{
    "subject": "Splunk Alert: Production ERROR/FATAL Monitor",
    "body_html": "<html>...<table>...</table>...</html>",
    "body_text": "Optional plain text fallback",
    "from": "splunk@example.com"
}
```

The email normalizer:

- Extracts the alert name from the subject line (strips "Splunk Alert:" prefix)
- Parses the HTML table into individual rows
- Creates one alert per row, using the same field extraction as the webhook normalizer
- If no explicit `service` field exists, derives it from the log path (e.g., `/opt/app/SERVICE_NAME/log/...` → `SERVICE_NAME`)
- Falls back to tab-delimited or pipe-delimited plain text if no HTML table is found
- Creates a single alert from the email body if no table is parseable

**To automate email forwarding**, set up a rule in your email client (Outlook rule, Power Automate flow, or a Python IMAP script) that forwards Splunk alert emails to an HTTP endpoint.

**Advantage over webhook:** Email ingestion sends ALL result rows from the search, while the Splunk webhook only sends the first row.

---

## How Alerts Work

### Lifecycle

```
firing → acknowledged → resolved
```

- **Firing** — Alert is active and needs attention
- **Acknowledged** — Someone is looking at it
- **Resolved** — Issue is fixed

### Deduplication

When Solace receives an alert, it generates a **fingerprint** from the alert's name, source, service, and host. If an alert with the same fingerprint was received within the dedup window (default 5 minutes), it's counted as a duplicate instead of creating a new alert.

The duplicate count is shown in the dashboard (e.g., "×3" means the same alert fired 3 times).

### Incidents

Alerts don't exist in isolation — they're automatically grouped into **incidents**.

**Correlation logic:** When a new alert arrives, Solace checks if there's an open incident for the same service within the correlation window (default 10 minutes). If yes, the alert is attached to that incident. If no, a new incident is created.

**Severity escalation:** An incident's severity is always the worst severity of its alerts. If a "warning" incident receives a "critical" alert, the incident escalates to "critical."

**Auto-resolve:** When all alerts in an incident are resolved, the incident auto-resolves.

**Example:** Three alerts arrive for the `payment-api` service from different hosts. Solace creates one incident titled "payment-api — HighCPU" with 3 correlated alerts. Acknowledging or resolving the incident applies to all alerts.

---

## Using the Dashboard

### Navigation

- **Incidents tab** — Shows grouped incidents. Click any incident to open the detail panel with correlated alerts, timeline, and actions.
- **Alerts tab** — Shows individual alerts with dedup counts.
- **On-Call tab** — Manage on-call schedules, escalation policies, and service mappings. Shows who's currently on call.
- **Silences tab** — Create and manage silence/maintenance windows.
- **Notifications tab** — Configure notification channels and view delivery logs.
- **Settings tab** — View app configuration, archive old alerts, and manage runbook rules (auto-attach runbook URLs to alerts by service/name pattern).
- **Users tab** (Admin only) — Create and manage user accounts.
- **Severity pills** (top bar) — Click to filter by severity level.
- **Status tabs** (All / Open / Acknowledged / Resolved) — Filter by status.
- **Theme toggle** — Switch between dark and light themes using the sun/moon icon in the header.
- **User menu** — Shows your name and role; click to logout.

### Search

- Click the search box or press `/` to focus
- Type to search across alert names, services, hosts, and descriptions
- Press `Escape` to clear

### Sorting

- Click any **column header** (Severity, Title, Status, Time, etc.) to sort
- Click again to reverse the sort order
- Active sort column shows an arrow indicator

### Stats Bar

The stats bar below the toolbar shows:

- **Active** — Currently firing alerts
- **Open Incidents** — Incidents needing attention
- **MTTA (24h)** — Mean Time to Acknowledge over the last 24 hours
- **MTTR (24h)** — Mean Time to Resolve over the last 24 hours
- **Total Alerts / Incidents** — All-time counts

### Detail Panels

Click any incident or alert to open its detail panel on the right:

- **Incident panel** — Shows severity, status, timing, correlated alerts (with expandable error details), timeline of events, and incident ID. Click any correlated alert to drill into its full detail view.
- **Alert panel** — Shows severity, status, tags, timing, attributes table, labels, annotations, raw payload viewer, links, and investigation notes.

Long error messages show a preview with a "Show more" button to expand the full text.

### Alert Detail Panel

Clicking an alert (either from the Alerts tab or from a correlated alert within an incident) opens the full alert detail panel:

- **Tags** — Teal-colored pills for quick categorization. Add tags by typing in the input and pressing Enter. Remove tags by clicking the × on each pill. Tags are stored as JSONB in PostgreSQL with a GIN index for future filtering support.
- **Timing** — When the alert started, duration, acknowledged/resolved timestamps.
- **Attributes** — Compact table showing Source, Service, Host, Environment, Fingerprint, Duplicates, and ID.
- **Labels** — Key=value metadata pills from the source system.
- **Annotations** — Extended context like runbook URLs, dashboards.
- **Raw Payload** — Collapsible JSON viewer showing the original webhook payload. Click to expand/collapse.
- **Links** — Link back to the source system (generator URL), editable runbook URL (with "Save as Rule" checkbox to auto-attach to future alerts), and external ticket URL.
- **Notes** — Timestamped investigation notes. Add notes with optional author attribution. Notes support create, update, and delete. Displayed newest-first.

### Actions

- **Acknowledge** — Marks an alert/incident as being worked on. Available on firing items.
- **Resolve** — Marks an alert/incident as fixed.
- **Acknowledge All / Resolve All** — On incidents, applies to all correlated alerts at once.

---

## API Reference

Base URL: `http://your-solace-host:8000/api/v1`

Full interactive docs available at: `http://your-solace-host:8000/docs`

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/login` | None | Login with username/password, returns JWT |
| `GET` | `/auth/me` | JWT | Get current user profile |
| `POST` | `/auth/change-password` | JWT | Change password |

### Users (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/users` | List users (paginated) |
| `POST` | `/users` | Create user |
| `PUT` | `/users/{id}` | Update user profile/role |
| `POST` | `/users/{id}/reset-password` | Reset user password |
| `DELETE` | `/users/{id}` | Deactivate user |

### Ingestion (API key auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhooks/generic` | Generic JSON alert |
| `POST` | `/webhooks/prometheus` | Prometheus Alertmanager payload |
| `POST` | `/webhooks/grafana` | Grafana unified alerting |
| `POST` | `/webhooks/datadog` | Datadog monitor webhook |
| `POST` | `/webhooks/splunk` | Splunk webhook payload |
| `POST` | `/webhooks/email_ingest` | Email-based alert ingestion |

### Alerts

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/alerts` | Any | List alerts (filterable, sortable, paginated) |
| `GET` | `/alerts/{id}` | Any | Get single alert by ID |
| `POST` | `/alerts/{id}/acknowledge` | User+ | Acknowledge an alert |
| `POST` | `/alerts/{id}/resolve` | User+ | Resolve an alert |
| `PUT` | `/alerts/{id}/tags` | User+ | Replace all tags on an alert |
| `POST` | `/alerts/{id}/tags/{tag}` | User+ | Add a single tag |
| `DELETE` | `/alerts/{id}/tags/{tag}` | User+ | Remove a single tag |
| `GET` | `/alerts/{id}/notes` | Any | List notes for an alert |
| `POST` | `/alerts/{id}/notes` | User+ | Add a note |
| `PUT` | `/alerts/notes/{note_id}` | User+ | Update a note |
| `DELETE` | `/alerts/notes/{note_id}` | User+ | Delete a note |
| `GET` | `/alerts/{id}/history` | Any | Get occurrence timeline |
| `PUT` | `/alerts/{id}/ticket` | User+ | Set external ticket URL |
| `PUT` | `/alerts/{id}/runbook` | User+ | Set runbook URL (optional `create_rule` flag) |
| `POST` | `/alerts/bulk/acknowledge` | User+ | Bulk acknowledge |
| `POST` | `/alerts/bulk/resolve` | User+ | Bulk resolve |
| `POST` | `/alerts/archive` | Admin | Archive old resolved alerts |

### Incidents

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/incidents` | Any | List incidents (filterable, sortable, paginated) |
| `GET` | `/incidents/{id}` | Any | Get incident with full alert list and timeline |
| `POST` | `/incidents/{id}/acknowledge` | User+ | Acknowledge incident + all alerts |
| `POST` | `/incidents/{id}/resolve` | User+ | Resolve incident + all alerts |

### On-Call Schedules

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/oncall/schedules` | Any | List schedules (paginated, `active_only` filter) |
| `POST` | `/oncall/schedules` | Admin | Create schedule |
| `GET` | `/oncall/schedules/{id}` | Any | Get schedule |
| `PUT` | `/oncall/schedules/{id}` | Admin | Update schedule |
| `DELETE` | `/oncall/schedules/{id}` | Admin | Delete schedule |
| `GET` | `/oncall/schedules/{id}/current` | Any | Get who is currently on call |
| `POST` | `/oncall/schedules/{id}/overrides` | Admin | Create temporary override |
| `DELETE` | `/oncall/overrides/{id}` | Admin | Delete override |

### Escalation Policies

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/oncall/policies` | Any | List escalation policies |
| `POST` | `/oncall/policies` | Admin | Create policy |
| `GET` | `/oncall/policies/{id}` | Any | Get policy |
| `PUT` | `/oncall/policies/{id}` | Admin | Update policy |
| `DELETE` | `/oncall/policies/{id}` | Admin | Delete policy |

### Service Mappings

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/oncall/mappings` | Any | List service-to-policy mappings |
| `POST` | `/oncall/mappings` | Admin | Create mapping |
| `DELETE` | `/oncall/mappings/{id}` | Admin | Delete mapping |

### Runbook Rules

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/runbooks/rules` | Any | List all runbook rules (ordered by priority) |
| `POST` | `/runbooks/rules` | Admin | Create runbook rule |
| `PUT` | `/runbooks/rules/{id}` | Admin | Update runbook rule |
| `DELETE` | `/runbooks/rules/{id}` | Admin | Delete runbook rule |

Runbook rules auto-attach runbook URLs to incoming alerts during ingestion. Each rule has a `service_pattern` (glob, e.g., `payment-*`), optional `name_pattern`, and a `runbook_url_template` with variables (`{service}`, `{host}`, `{name}`, `{environment}`). Rules are evaluated by priority (lower = first); first match wins. Managed from **Settings > Runbook Rules** in the dashboard.

### Silences (Maintenance Windows)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/silences` | Any | List silence windows |
| `POST` | `/silences` | Admin | Create silence window |
| `GET` | `/silences/{id}` | Any | Get silence window |
| `PUT` | `/silences/{id}` | Admin | Update silence window |
| `DELETE` | `/silences/{id}` | Admin | Delete silence window |

### Notification Channels

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `GET` | `/notifications/channels` | Any | List all channels |
| `POST` | `/notifications/channels` | Admin | Create channel |
| `GET` | `/notifications/channels/{id}` | Any | Get channel |
| `PUT` | `/notifications/channels/{id}` | Admin | Update channel |
| `DELETE` | `/notifications/channels/{id}` | Admin | Delete channel |
| `POST` | `/notifications/channels/{id}/test` | Admin | Send test notification |
| `GET` | `/notifications/logs` | Any | List delivery logs |

### Stats & Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/stats` | Dashboard statistics (MTTA, MTTR, counts by status/severity) |
| `GET` | `/settings` | Application configuration |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Basic health check |
| `GET` | `/health/ready` | Readiness check (verifies DB and Redis connections) |

---

## Troubleshooting

### Alerts not showing up

1. Check the API is running: `curl http://localhost:8000/health`
2. Check the webhook response: the POST should return `202 Accepted` with an `alert_id`
3. Check API logs: `docker compose logs solace-api --tail 50`
4. Verify the provider name in the URL matches (`splunk`, `email`, `generic`, `prometheus`)

### Alerts not correlating into incidents

Alerts only correlate if they share the same `service` value and arrive within the correlation window (default 10 minutes). Check:

- Does your SPL query include a `service` field? If not, the normalizer tries to derive it from `sourcetype`, `app`, or the log path.
- Are the alerts arriving more than 10 minutes apart? Increase `CORRELATION_WINDOW_SECONDS` if needed.

### Duplicate alerts not being deduplicated

Dedup is based on fingerprint (name + source + service + host). Two alerts must match ALL of these fields to be considered duplicates. Check that your alerts have consistent field values.

### Dashboard not loading

1. Check the frontend container: `docker compose logs solace-frontend --tail 20`
2. Verify port 3000 is accessible
3. Check the API URL — the frontend proxies API calls to port 8000

### Rebuilding from scratch

```bash
docker compose down -v    # -v removes volumes (deletes all data)
docker compose up --build -d
```

---

## Testing

### Local test commands

After deploying, send test alerts to verify everything works:

```bash
# Test Splunk webhook
curl -X POST http://localhost:8000/api/v1/webhooks/splunk \
  -H "Content-Type: application/json" \
  -d '{
    "result": {
      "host": "test-webapp-1.company.com",
      "severity": "high",
      "service": "test-app",
      "message": "Test alert from Solace documentation"
    },
    "sid": "scheduler_admin_test_001",
    "results_link": "http://splunk:8000/app/search/@go?sid=test",
    "search_name": "Documentation Test Alert",
    "owner": "admin",
    "app": "search"
  }'

# Test email ingestion
curl -X POST http://localhost:8000/api/v1/webhooks/email \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Splunk Alert: Documentation Test",
    "body_html": "<table><tr><th>host</th><th>message</th></tr><tr><td>test-host</td><td>Test error message</td></tr></table>",
    "from": "splunk@example.com"
  }'
```

### Running automated tests

```bash
cd solace
pip install -e ".[dev]"
pytest tests/ -v
```

Current test coverage: 95 tests covering webhook ingestion, normalization (generic, Prometheus, Splunk, email), deduplication, correlation, and API endpoints.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, async SQLAlchemy, Alembic, python-jose (JWT), passlib (bcrypt) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Deployment | Docker, Docker Compose |
| CI/CD | GitHub Actions (lint, test, build) |

---

## Roadmap

### Completed
- ~~Notification channels (Slack, Teams, Email, Webhook, PagerDuty)~~ ✅
- ~~Silence / maintenance windows (suppress alerts during deployments)~~ ✅
- ~~Grafana and Datadog normalizers~~ ✅
- ~~Alert tagging and investigation notes~~ ✅
- ~~JWT authentication and default admin account~~ ✅
- ~~Role-based access control (admin, user, viewer)~~ ✅
- ~~User management (create, edit, deactivate)~~ ✅
- ~~On-call scheduling (hourly/daily/weekly/custom rotations)~~ ✅
- ~~Escalation policies with multi-level targets~~ ✅
- ~~Service-to-policy mapping with glob patterns~~ ✅
- ~~Light and dark theme toggle~~ ✅
- ~~Runbook rules (auto-attach runbook URLs to alerts by pattern)~~ ✅

### Next Up
- SSO integration (Google, GitHub, SAML)
- Background escalation checker (auto-escalate unacknowledged incidents)
- SMS and voice call notifications (Twilio)
- Metrics and SLA reporting
- Status pages
