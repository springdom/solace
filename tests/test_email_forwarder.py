"""Tests for the email forwarder script."""

import argparse
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

# The email forwarder is a standalone script that depends on `requests`,
# which is not a core backend dependency. Skip the entire module if missing.
pytest.importorskip("requests", reason="requests is required for email forwarder tests")

# Add the forwarder script to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "email_forwarder"))

from forwarder import (
    build_config,
    forward_to_solace,
    matches_subject,
    parse_email,
)

# ─── Email Parsing Tests ───────────────────────────────


class TestParseEmail:
    def test_plain_text_email(self):
        msg = MIMEText("Alert: CPU high on web-01", "plain")
        msg["Subject"] = "Splunk Alert: CPU Monitor"
        msg["From"] = "splunk@example.com"
        msg["To"] = "alerts@example.com"

        result = parse_email(msg)
        assert result["subject"] == "Splunk Alert: CPU Monitor"
        assert result["body_text"] == "Alert: CPU high on web-01"
        assert result["body_html"] == ""
        assert result["from"] == "splunk@example.com"
        assert result["to"] == "alerts@example.com"

    def test_html_email(self):
        msg = MIMEText("<html><body><table><tr><th>host</th></tr></table></body></html>", "html")
        msg["Subject"] = "Splunk Alert: Errors"
        msg["From"] = "splunk@example.com"
        msg["To"] = "alerts@example.com"

        result = parse_email(msg)
        assert result["subject"] == "Splunk Alert: Errors"
        assert "<table>" in result["body_html"]
        assert result["body_text"] == ""

    def test_multipart_email(self):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Splunk Alert: Multi"
        msg["From"] = "splunk@example.com"
        msg["To"] = "alerts@example.com"

        text_part = MIMEText("Plain text version", "plain")
        html_part = MIMEText("<html><body>HTML version</body></html>", "html")
        msg.attach(text_part)
        msg.attach(html_part)

        result = parse_email(msg)
        assert result["body_text"] == "Plain text version"
        assert "HTML version" in result["body_html"]

    def test_missing_headers_use_defaults(self):
        msg = MIMEText("body", "plain")
        # No Subject, From, To headers

        result = parse_email(msg)
        assert result["subject"] == ""
        assert result["from"] == ""
        assert result["to"] == ""


# ─── Subject Matching Tests ─────────────────────────────


class TestSubjectMatching:
    def test_substring_match(self):
        assert matches_subject("Splunk Alert: CPU High", "Splunk Alert") is True

    def test_substring_case_insensitive(self):
        assert matches_subject("SPLUNK ALERT: CPU HIGH", "splunk alert") is True

    def test_no_match(self):
        assert matches_subject("Weekly Report", "Splunk Alert") is False

    def test_regex_match(self):
        assert matches_subject("Splunk Alert: CPU High", r"Splunk Alert:\s+\w+") is True

    def test_empty_pattern_matches_all(self):
        assert matches_subject("Anything goes", "") is True

    def test_regex_with_alternation(self):
        assert matches_subject("Datadog Alert: CPU High", r"Splunk|Datadog") is True
        assert matches_subject("Grafana Warning", r"Splunk|Datadog") is False


# ─── Forward to Solace Tests ────────────────────────────


class TestForwardToSolace:
    def test_successful_forward(self):
        config = {"solace_url": "http://localhost:8000", "solace_api_key": "test-key"}
        payload = {
            "subject": "Test", "body_html": "<html>test</html>",
            "body_text": "", "from": "", "to": "",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {
            "alert_id": "abc", "fingerprint": "def", "is_duplicate": False,
        }

        with patch("forwarder.requests.post", return_value=mock_resp) as mock_post:
            result = forward_to_solace(payload, config)

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"]["X-API-Key"] == "test-key"

    def test_failed_forward(self):
        config = {"solace_url": "http://localhost:8000", "solace_api_key": ""}
        payload = {"subject": "Test", "body_html": "", "body_text": "", "from": "", "to": ""}

        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Payload validation error"

        with patch("forwarder.requests.post", return_value=mock_resp):
            result = forward_to_solace(payload, config)

        assert result is False

    def test_network_error(self):
        config = {"solace_url": "http://localhost:8000", "solace_api_key": ""}
        payload = {"subject": "Test", "body_html": "", "body_text": "", "from": "", "to": ""}

        import requests as req
        with patch("forwarder.requests.post", side_effect=req.ConnectionError("refused")):
            result = forward_to_solace(payload, config)

        assert result is False

    def test_no_api_key_omits_header(self):
        config = {"solace_url": "http://localhost:8000", "solace_api_key": ""}
        payload = {"subject": "Test", "body_html": "", "body_text": "", "from": "", "to": ""}

        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {}

        with patch("forwarder.requests.post", return_value=mock_resp) as mock_post:
            forward_to_solace(payload, config)

        headers = mock_post.call_args.kwargs["headers"]
        assert "X-API-Key" not in headers


# ─── Config Tests ───────────────────────────────────────


class TestBuildConfig:
    def test_defaults(self):
        args = argparse.Namespace(
            imap_host=None, imap_port=None, imap_user=None, imap_password=None,
            imap_use_ssl=None, imap_folder=None, subject_pattern=None,
            solace_url=None, solace_api_key=None, poll_interval=None,
            mark_as_read=None, move_to_folder=None,
        )
        # Clear env vars that might interfere
        for key in ["IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"]:
            os.environ.pop(key, None)

        config = build_config(args)
        assert config["imap_port"] == 993
        assert config["imap_use_ssl"] is True
        assert config["imap_folder"] == "INBOX"
        assert config["subject_pattern"] == "Splunk Alert"
        assert config["poll_interval"] == 60

    def test_cli_overrides_env(self):
        os.environ["IMAP_HOST"] = "env-host.example.com"
        args = argparse.Namespace(
            imap_host="cli-host.example.com", imap_port=None, imap_user=None,
            imap_password=None, imap_use_ssl=None, imap_folder=None,
            subject_pattern=None, solace_url=None, solace_api_key=None,
            poll_interval=None, mark_as_read=None, move_to_folder=None,
        )

        config = build_config(args)
        assert config["imap_host"] == "cli-host.example.com"

        # Clean up
        os.environ.pop("IMAP_HOST", None)
