<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status: Alpha" />
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT" />
</p>

# Solace

Open-source alert management and incident response platform. Ingest alerts from any monitoring source, deduplicate them, auto-correlate into incidents, and manage the response — all from a single dashboard.

**Think PagerDuty / Opsgenie, but open-source and self-hosted.**

## Features

- **Multi-source ingestion** — Generic webhook, Prometheus Alertmanager, Splunk webhook, and Splunk email ingestion normalizers, with a pluggable architecture for Grafana, Datadog, etc.
- **Fingerprint-based deduplication** — Identical alerts are counted, not duplicated. Configurable dedup window.
- **Automatic incident correlation** — Alerts from the same service are grouped into incidents within a configurable time window. Severity auto-promotes to the worst alert.
- **Full audit trail** — Every incident action (created, alert added, severity changed, acknowledged, resolved) is recorded as a timeline event.
- **Auto-resolve** — When all alerts in an incident resolve, the incident auto-resolves.
- **Dark ops-console dashboard** — Real-time React UI with incident/alert views, severity badges, detail panels, and one-click ack/resolve.

## Architecture

```
Prometheus ─┐
Grafana ────┤                   ┌─────────────┐     ┌────────────┐
Datadog ────┼─▶ Webhook API ──▶ │ Normalizer  │ ──▶ │  Dedup     │
Splunk ─────┤   (FastAPI)       │ (pluggable) │     │  Engine    │
Email ──────┤
Custom ─────┘                   └─────────────┘     └─────┬──────┘
                                                          │
                                                    ┌─────▼──────┐
                                                    │ Correlation │
                                                    │   Engine    │
                                                    └─────┬──────┘
                                                          │
                                              ┌───────────▼───────────┐
                                              │  PostgreSQL (alerts,  │
                                              │  incidents, events)   │
                                              └───────────┬───────────┘
                                                          │
                                              ┌───────────▼───────────┐
                                              │  React Dashboard      │
                                              │  (Vite + Tailwind)    │
                                              └───────────────────────┘
```

## Quick Start

### Docker Compose (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/solace.git
cd solace
docker compose up --build
```

- **Dashboard:** http://localhost:3000
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

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
    "description": "CPU usage above 95% for 10 minutes"
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

# Splunk webhook alert
curl -X POST http://localhost:8000/api/v1/webhooks/splunk \
  -H "Content-Type: application/json" \
  -d '{
    "result": {
      "host": "web-01",
      "severity": "critical",
      "service": "payment-api",
      "message": "CPU usage above 95% for 10 minutes",
      "sourcetype": "syslog",
      "avg_cpu": "97.3"
    },
    "sid": "scheduler_admin_HighCPU_at_17000000_132",
    "results_link": "http://splunk:8000/app/search/@go?sid=scheduler_admin_HighCPU",
    "search_name": "High CPU Usage Alert",
    "owner": "admin",
    "app": "search"
  }'
```

### Email ingestion (forward Splunk alert emails)

Instead of configuring webhooks in Splunk, you can forward alert emails directly:

```bash
# POST the email content as JSON — parses HTML tables from Splunk emails
curl -X POST http://localhost:8000/api/v1/webhooks/email \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Splunk Alert: Production ERROR/FATAL Monitor",
    "body_html": "<table><tr><th>host</th><th>source</th><th>message</th><th>_raw</th></tr><tr><td>web-01</td><td>/opt/apps/myapp/log/myapp.log</td><td>ERROR</td><td>Connection refused</td></tr></table>",
    "from": "splunk@example.com",
    "to": "alerts@company.com"
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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/health/ready` | Readiness check (DB + Redis) |
| `POST` | `/api/v1/webhooks/{provider}` | Ingest alert webhook |
| `GET` | `/api/v1/alerts` | List alerts (filterable) |
| `GET` | `/api/v1/alerts/{id}` | Get alert by ID |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| `POST` | `/api/v1/alerts/{id}/resolve` | Resolve alert |
| `GET` | `/api/v1/incidents` | List incidents (filterable) |
| `GET` | `/api/v1/incidents/{id}` | Get incident with alerts + events |
| `POST` | `/api/v1/incidents/{id}/acknowledge` | Acknowledge incident + all alerts |
| `POST` | `/api/v1/incidents/{id}/resolve` | Resolve incident + all alerts |

## Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://solace:solace@localhost:5432/solace` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `DEDUP_WINDOW_SECONDS` | `300` | Window for deduplicating identical alerts (5 min) |
| `CORRELATION_WINDOW_SECONDS` | `600` | Window for correlating alerts into incidents (10 min) |
| `APP_ENV` | `development` | Environment (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Tech Stack

**Backend:** Python 3.11+, FastAPI, async SQLAlchemy, Alembic, PostgreSQL, Redis

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS

## Development

### Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
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

- [ ] Grafana normalizer
- [ ] Datadog normalizer
- [ ] On-call scheduling and escalation policies
- [ ] Notification channels (Slack, email, PagerDuty bridge)
- [ ] Silence / maintenance windows
- [ ] RBAC and multi-tenancy
- [ ] Topology-aware correlation (service dependency graph)
- [ ] Metrics and SLA tracking (MTTA, MTTR)

## License

MIT
