# Solace Email Forwarder

Standalone IMAP poller that forwards alert emails (e.g. from Splunk) to the Solace webhook API.

## How it works

1. Connects to an IMAP mailbox via SSL
2. Fetches unread emails matching a configurable subject pattern
3. Parses email subject, HTML body, and plain text body
4. POSTs the parsed content to `POST /api/v1/webhooks/email`
5. Marks processed emails as read (and optionally moves them to a folder)
6. Repeats on a configurable interval

## Quick start

```bash
# Set required env vars
export IMAP_HOST=mail.example.com
export IMAP_USER=alerts@example.com
export IMAP_PASSWORD=secret
export SOLACE_URL=http://localhost:8000
export SOLACE_API_KEY=your-integration-api-key

# Install dependency
pip install requests

# Run
python forwarder.py
```

## Configuration

All settings can be set via environment variables or CLI arguments (CLI takes precedence).

| Env Variable | CLI Flag | Default | Description |
|---|---|---|---|
| `IMAP_HOST` | `--imap-host` | *(required)* | IMAP server hostname |
| `IMAP_PORT` | `--imap-port` | `993` | IMAP server port |
| `IMAP_USER` | `--imap-user` | *(required)* | IMAP username |
| `IMAP_PASSWORD` | `--imap-password` | *(required)* | IMAP password |
| `IMAP_USE_SSL` | `--imap-use-ssl` | `true` | Use SSL for IMAP |
| `IMAP_FOLDER` | `--imap-folder` | `INBOX` | IMAP folder to poll |
| `SUBJECT_PATTERN` | `--subject-pattern` | `Splunk Alert` | Subject filter (substring or regex) |
| `SOLACE_URL` | `--solace-url` | `http://localhost:8000` | Solace API base URL |
| `SOLACE_API_KEY` | `--solace-api-key` | *(empty)* | Solace integration API key |
| `POLL_INTERVAL` | `--poll-interval` | `60` | Seconds between polls |
| `MARK_AS_READ` | `--mark-as-read` | `true` | Mark emails as read after processing |
| `MOVE_TO_FOLDER` | `--move-to-folder` | *(empty)* | Move processed emails to this IMAP folder |
| `MAX_EMAILS_PER_POLL` | — | `50` | Max emails to process per poll cycle |

## Deployment options

### Docker

```bash
docker build -t solace-email-forwarder .
docker run -d \
  -e IMAP_HOST=mail.example.com \
  -e IMAP_USER=alerts@example.com \
  -e IMAP_PASSWORD=secret \
  -e SOLACE_URL=http://solace-api:8000 \
  -e SOLACE_API_KEY=your-key \
  solace-email-forwarder
```

### systemd

```bash
# Copy files
sudo mkdir -p /opt/solace/email-forwarder
sudo cp forwarder.py /opt/solace/email-forwarder/
cd /opt/solace/email-forwarder && python3 -m venv venv && venv/bin/pip install requests

# Create env file with credentials
sudo mkdir -p /etc/solace
sudo tee /etc/solace/email-forwarder.env <<EOF
IMAP_HOST=mail.example.com
IMAP_USER=alerts@example.com
IMAP_PASSWORD=secret
SOLACE_URL=http://localhost:8000
SOLACE_API_KEY=your-key
EOF
sudo chmod 600 /etc/solace/email-forwarder.env

# Install and start service
sudo cp solace-email-forwarder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now solace-email-forwarder
```

### One-shot mode

Run once and exit (useful for cron):

```bash
python forwarder.py --once
```
