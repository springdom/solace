#!/usr/bin/env python3
"""Solace Email Forwarder — IMAP poller that forwards alert emails to Solace.

Polls an IMAP mailbox for alert emails (e.g. from Splunk) and forwards
them to the Solace webhook API as structured payloads that the email
normalizer can process.

Usage:
    # Environment variables (or CLI args):
    export IMAP_HOST=mail.example.com
    export IMAP_USER=alerts@example.com
    export IMAP_PASSWORD=secret
    export SOLACE_URL=http://localhost:8000
    export SOLACE_API_KEY=your-integration-api-key

    python forwarder.py

    # Or with CLI overrides:
    python forwarder.py --imap-host mail.example.com --poll-interval 30
"""

import argparse
import email
import email.utils
import imaplib
import logging
import os
import re
import signal
import sys
import time
from email.message import Message

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("solace-email-forwarder")

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum: int, frame: object) -> None:
    global _shutdown
    logger.info(f"Received signal {signum}, shutting down...")
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Configuration ────────────────────────────────────────


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: str = "true") -> bool:
    return _env(key, default).lower() == "true"


def build_config(args: argparse.Namespace) -> dict:
    """Build configuration from env vars with CLI overrides."""
    ssl = args.imap_use_ssl
    if ssl is None:
        ssl = _env_bool("IMAP_USE_SSL")
    read = args.mark_as_read
    if read is None:
        read = _env_bool("MARK_AS_READ")

    return {
        "imap_host": args.imap_host or _env("IMAP_HOST"),
        "imap_port": args.imap_port or int(_env("IMAP_PORT", "993")),
        "imap_user": args.imap_user or _env("IMAP_USER"),
        "imap_password": args.imap_password or _env("IMAP_PASSWORD"),
        "imap_use_ssl": ssl,
        "imap_folder": args.imap_folder or _env("IMAP_FOLDER", "INBOX"),
        "subject_pattern": (
            args.subject_pattern or _env("SUBJECT_PATTERN", "Splunk Alert")
        ),
        "solace_url": (
            args.solace_url or _env("SOLACE_URL", "http://localhost:8000")
        ),
        "solace_api_key": args.solace_api_key or _env("SOLACE_API_KEY"),
        "poll_interval": (
            args.poll_interval or int(_env("POLL_INTERVAL", "60"))
        ),
        "mark_as_read": read,
        "move_to_folder": args.move_to_folder or _env("MOVE_TO_FOLDER"),
        "max_emails_per_poll": int(_env("MAX_EMAILS_PER_POLL", "50")),
    }


# ── Email parsing ────────────────────────────────────────


def parse_email(msg: Message) -> dict:
    """Extract structured fields from an email Message.

    Returns a dict matching the Solace email webhook payload format:
    {subject, body_html, body_text, from, to}
    """
    subject = msg.get("Subject", "")
    # Decode subject if it's encoded (e.g. =?utf-8?q?...)
    decoded_parts = email.header.decode_header(subject)
    subject = "".join(
        part.decode(charset or "utf-8") if isinstance(part, bytes) else part
        for part, charset in decoded_parts
    )

    sender = msg.get("From", "")
    to = msg.get("To", "")

    body_html = ""
    body_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_html = payload.decode(charset, errors="replace")
            elif content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                body_html = decoded
            else:
                body_text = decoded

    return {
        "subject": subject,
        "body_html": body_html,
        "body_text": body_text,
        "from": sender,
        "to": to,
    }


def matches_subject(subject: str, pattern: str) -> bool:
    """Check if an email subject matches the configured pattern.

    Supports simple substring matching and basic regex.
    """
    if not pattern:
        return True
    # Try regex first
    try:
        if re.search(pattern, subject, re.IGNORECASE):
            return True
    except re.error:
        pass
    # Fall back to case-insensitive substring
    return pattern.lower() in subject.lower()


# ── IMAP operations ──────────────────────────────────────


def connect_imap(config: dict) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
    """Connect and authenticate to IMAP server."""
    if config["imap_use_ssl"]:
        conn = imaplib.IMAP4_SSL(config["imap_host"], config["imap_port"])
    else:
        conn = imaplib.IMAP4(config["imap_host"], config["imap_port"])

    conn.login(config["imap_user"], config["imap_password"])
    return conn


def fetch_unread_emails(conn: imaplib.IMAP4, config: dict) -> list[tuple[str, Message]]:
    """Fetch unread emails from the configured folder.

    Returns list of (uid, Message) tuples.
    """
    conn.select(config["imap_folder"])

    # Search for unseen emails
    status, data = conn.uid("search", None, "UNSEEN")
    if status != "OK" or not data[0]:
        return []

    uids = data[0].split()
    # Limit to prevent overwhelming the system
    uids = uids[: config["max_emails_per_poll"]]

    results = []
    for uid in uids:
        uid_str = uid.decode() if isinstance(uid, bytes) else uid
        status, msg_data = conn.uid("fetch", uid_str, "(RFC822)")
        if status != "OK" or not msg_data[0]:
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        results.append((uid_str, msg))

    return results


def mark_processed(conn: imaplib.IMAP4, uid: str, config: dict) -> None:
    """Mark an email as processed — flag as read and optionally move."""
    if config["mark_as_read"]:
        conn.uid("store", uid, "+FLAGS", "\\Seen")

    if config["move_to_folder"]:
        # Create folder if it doesn't exist (ignore error if it does)
        conn.create(config["move_to_folder"])
        conn.uid("copy", uid, config["move_to_folder"])
        conn.uid("store", uid, "+FLAGS", "\\Deleted")
        conn.expunge()


# ── Solace API ───────────────────────────────────────────


def forward_to_solace(payload: dict, config: dict) -> bool:
    """POST parsed email to Solace webhook endpoint.

    Returns True on success, False on failure.
    """
    url = f"{config['solace_url'].rstrip('/')}/api/v1/webhooks/email"
    headers = {"Content-Type": "application/json"}

    if config["solace_api_key"]:
        headers["X-API-Key"] = config["solace_api_key"]

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 202:
            data = resp.json()
            logger.info(
                f"Forwarded: alert_id={data.get('alert_id', 'N/A')}, "
                f"fingerprint={data.get('fingerprint', 'N/A')}, "
                f"duplicate={data.get('is_duplicate', False)}"
            )
            return True
        else:
            logger.warning(f"Solace returned {resp.status_code}: {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        logger.error(f"Failed to forward to Solace: {e}")
        return False


# ── Main loop ────────────────────────────────────────────


def poll_once(config: dict) -> int:
    """Run a single poll cycle. Returns number of emails forwarded."""
    conn = None
    forwarded = 0

    try:
        conn = connect_imap(config)
        emails = fetch_unread_emails(conn, config)

        if not emails:
            logger.debug("No unread emails found")
            return 0

        logger.info(f"Found {len(emails)} unread email(s)")

        for uid, msg in emails:
            subject = msg.get("Subject", "")
            if not matches_subject(subject, config["subject_pattern"]):
                logger.debug(f"Skipping email (no match): {subject[:60]}")
                continue

            logger.info(f"Processing: {subject[:80]}")
            payload = parse_email(msg)

            if forward_to_solace(payload, config):
                mark_processed(conn, uid, config)
                forwarded += 1
            else:
                logger.warning(f"Failed to forward email uid={uid}, will retry next poll")

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during poll: {e}")
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass

    return forwarded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Solace Email Forwarder — forward alert emails to Solace",
    )
    parser.add_argument("--imap-host", help="IMAP server hostname")
    parser.add_argument("--imap-port", type=int, help="IMAP server port (default: 993)")
    parser.add_argument("--imap-user", help="IMAP username")
    parser.add_argument("--imap-password", help="IMAP password")
    parser.add_argument("--imap-use-ssl", type=bool, default=None, help="Use SSL for IMAP")
    parser.add_argument("--imap-folder", help="IMAP folder to poll (default: INBOX)")
    parser.add_argument(
        "--subject-pattern",
        help="Subject filter pattern (default: 'Splunk Alert')",
    )
    parser.add_argument("--solace-url", help="Solace API base URL")
    parser.add_argument("--solace-api-key", help="Solace integration API key")
    parser.add_argument(
        "--poll-interval", type=int, help="Seconds between polls (default: 60)",
    )
    parser.add_argument(
        "--mark-as-read", type=bool, default=None,
        help="Mark emails as read after processing",
    )
    parser.add_argument("--move-to-folder", help="Move processed emails to this IMAP folder")
    parser.add_argument("--once", action="store_true", help="Run once and exit (no polling loop)")

    args = parser.parse_args()
    config = build_config(args)

    # Validate required config
    if not config["imap_host"]:
        logger.error("IMAP_HOST is required (set env var or --imap-host)")
        sys.exit(1)
    if not config["imap_user"]:
        logger.error("IMAP_USER is required (set env var or --imap-user)")
        sys.exit(1)
    if not config["imap_password"]:
        logger.error("IMAP_PASSWORD is required (set env var or --imap-password)")
        sys.exit(1)

    logger.info("Solace Email Forwarder starting")
    logger.info(f"  IMAP: {config['imap_user']}@{config['imap_host']}:{config['imap_port']}")
    logger.info(f"  Folder: {config['imap_folder']}")
    logger.info(f"  Subject pattern: {config['subject_pattern']}")
    logger.info(f"  Solace URL: {config['solace_url']}")
    logger.info(f"  Poll interval: {config['poll_interval']}s")

    if args.once:
        count = poll_once(config)
        logger.info(f"Single poll complete: {count} email(s) forwarded")
        return

    # Polling loop
    while not _shutdown:
        count = poll_once(config)
        if count > 0:
            logger.info(f"Poll complete: {count} email(s) forwarded")

        # Sleep in small increments for responsive shutdown
        for _ in range(config["poll_interval"]):
            if _shutdown:
                break
            time.sleep(1)

    logger.info("Forwarder stopped")


if __name__ == "__main__":
    main()
