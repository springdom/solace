"""Tests for the email ingestion normalizer."""

from backend.integrations.email_ingest import (
    EmailNormalizer,
    _extract_search_name,
    parse_html_tables,
    parse_plain_text_table,
)

# ─── Realistic Splunk alert email (based on user's actual query output) ───

SPLUNK_HTML_EMAIL = {
    "subject": "Splunk Alert: Production ERROR/FATAL Monitor",
    "body_html": """
    <html>
    <body>
    <p>The following alert has been triggered:</p>
    <p><b>Name:</b> Production ERROR/FATAL Monitor</p>
    <table border="1">
    <tr>
        <th>host</th>
        <th>source</th>
        <th>message</th>
        <th>_raw</th>
    </tr>
    <tr>
        <td>app-prod-web-2.internal.example.com</td>
        <td>/opt/apps/billing-svc/logs/billing-svc.log</td>
        <td>ERROR</td>
        <td>2026-02-12 04:10:57.489 [ajp-nio-10.0.0.2-10022-exec-2]
ERROR o.a.c.c.C - dispatcherServlet threw exception</td>
    </tr>
    <tr>
        <td>app-prod-web-2.internal.example.com</td>
        <td>/opt/apps/billing-svc/logs/billing-svc.log</td>
        <td>ERROR</td>
        <td>2026-02-12 04:10:57.489 ERROR -
Connection prematurely closed BEFORE response</td>
    </tr>
    <tr>
        <td>app-prod-web-1.internal.example.com</td>
        <td>/opt/apps/order-svc/log/order-svc.log</td>
        <td>FATAL</td>
        <td>2026-02-12 04:12:00.000 FATAL OutOfMemoryError: Java heap space</td>
    </tr>
    </table>
    </body>
    </html>
    """,
    "body_text": "",
    "from": "splunk@example.com",
    "to": "alerts@example.com",
}

# Aggregated query results (what the recommended SPL produces)
SPLUNK_AGGREGATED_EMAIL = {
    "subject": "Splunk Alert: Production ERROR/FATAL Monitor",
    "body_html": """
    <html>
    <body>
    <table>
    <tr><th>source</th><th>message</th><th>error_count</th><th>affected_hosts</th>
        <th>host</th><th>severity</th><th>service</th><th>latest_error</th></tr>
    <tr>
        <td>/opt/apps/billing-svc/logs/billing-svc.log</td>
        <td>ERROR</td>
        <td>27</td>
        <td>2</td>
        <td>app-prod-web-2.internal.example.com</td>
        <td>high</td>
        <td>billing-svc</td>
        <td>Connection prematurely closed BEFORE response</td>
    </tr>
    <tr>
        <td>/opt/apps/order-svc/log/order-svc.log</td>
        <td>FATAL</td>
        <td>3</td>
        <td>1</td>
        <td>app-prod-web-1.internal.example.com</td>
        <td>critical</td>
        <td>order-svc</td>
        <td>FATAL OutOfMemoryError: Java heap space</td>
    </tr>
    </table>
    </body>
    </html>
    """,
    "from": "splunk@example.com",
    "to": "alerts@example.com",
}

PLAIN_TEXT_EMAIL = {
    "subject": "Splunk Alert: Disk Space Warning",
    "body_text": (
        "host\tsource\tmessage\n"
        "db-01\t/var/log/syslog\tDisk 95% full\n"
        "db-02\t/var/log/syslog\tDisk 88% full"
    ),
    "from": "splunk@example.com",
    "to": "alerts@company.com",
}

MINIMAL_EMAIL = {
    "subject": "Splunk Alert: Something Happened",
    "body_text": "An alert was triggered but no table data is available.",
    "from": "splunk@example.com",
    "to": "alerts@company.com",
}


class TestExtractSearchName:
    def test_standard_colon_format(self):
        assert _extract_search_name("Splunk Alert: High CPU Usage") == "High CPU Usage"

    def test_dash_format(self):
        assert _extract_search_name("Splunk Alert - High CPU Usage") == "High CPU Usage"

    def test_bracket_format(self):
        assert _extract_search_name("[Splunk] High CPU Usage") == "High CPU Usage"

    def test_custom_subject(self):
        assert _extract_search_name("Production Errors Detected") == "Production Errors Detected"

    def test_empty_subject(self):
        assert _extract_search_name("") == "Splunk Email Alert"

    def test_case_insensitive(self):
        assert _extract_search_name("SPLUNK ALERT: Test") == "Test"


class TestHTMLTableParsing:
    def test_basic_table(self):
        html = """
        <table>
        <tr><th>host</th><th>message</th></tr>
        <tr><td>web-01</td><td>ERROR</td></tr>
        <tr><td>web-02</td><td>FATAL</td></tr>
        </table>
        """
        tables = parse_html_tables(html)
        assert len(tables) == 1
        assert len(tables[0]) == 2
        assert tables[0][0]["host"] == "web-01"
        assert tables[0][1]["message"] == "FATAL"

    def test_nested_tags_in_cells(self):
        html = """
        <table>
        <tr><th>host</th><th>link</th></tr>
        <tr><td><b>web-01</b></td><td><a href="#">Click</a> here</td></tr>
        </table>
        """
        tables = parse_html_tables(html)
        assert tables[0][0]["host"] == "web-01"
        assert tables[0][0]["link"] == "Click here"

    def test_multiple_tables_picks_largest(self):
        """EmailNormalizer should use the largest table."""
        html = """
        <table><tr><th>key</th></tr><tr><td>val</td></tr></table>
        <table>
            <tr><th>host</th><th>msg</th></tr>
            <tr><td>a</td><td>1</td></tr>
            <tr><td>b</td><td>2</td></tr>
            <tr><td>c</td><td>3</td></tr>
        </table>
        """
        tables = parse_html_tables(html)
        assert len(tables) == 2
        largest = max(tables, key=len)
        assert len(largest) == 3

    def test_empty_table(self):
        html = "<table></table>"
        tables = parse_html_tables(html)
        assert tables == []

    def test_thead_tbody(self):
        html = """
        <table>
        <thead><tr><th>host</th><th>level</th></tr></thead>
        <tbody>
        <tr><td>db-01</td><td>critical</td></tr>
        </tbody>
        </table>
        """
        tables = parse_html_tables(html)
        assert len(tables) == 1
        assert tables[0][0]["host"] == "db-01"


class TestPlainTextParsing:
    def test_tab_delimited(self):
        text = "host\tsource\tmessage\nweb-01\t/var/log\tERROR\nweb-02\t/var/log\tFATAL"
        rows = parse_plain_text_table(text)
        assert len(rows) == 2
        assert rows[0]["host"] == "web-01"
        assert rows[1]["message"] == "FATAL"

    def test_pipe_delimited(self):
        text = "host | source | message\nweb-01 | /var/log | ERROR"
        rows = parse_plain_text_table(text)
        assert len(rows) == 1
        assert rows[0]["host"] == "web-01"

    def test_no_table(self):
        text = "This is just a plain text alert with no table structure."
        rows = parse_plain_text_table(text)
        assert rows == []


class TestEmailValidation:
    def test_valid_html_email(self):
        n = EmailNormalizer()
        assert n.validate(SPLUNK_HTML_EMAIL) is True

    def test_valid_text_email(self):
        n = EmailNormalizer()
        assert n.validate(PLAIN_TEXT_EMAIL) is True

    def test_invalid_no_subject(self):
        n = EmailNormalizer()
        assert n.validate({"body_html": "<table></table>"}) is False

    def test_invalid_no_body(self):
        n = EmailNormalizer()
        assert n.validate({"subject": "test"}) is False


class TestEmailNormalization:
    def test_html_email_produces_multiple_alerts(self):
        """Your actual Splunk email format with 3 result rows."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        assert len(alerts) == 3

        # All should have the search name from the subject
        for a in alerts:
            assert a.name == "Production ERROR/FATAL Monitor"
            assert a.source == "splunk"
            assert a.status == "firing"

    def test_html_email_extracts_hosts(self):
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        hosts = [a.host for a in alerts]
        assert "app-prod-web-2.internal.example.com" in hosts
        assert "app-prod-web-1.internal.example.com" in hosts

    def test_html_email_extracts_service_from_path(self):
        """Service should be derived from the log path."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        services = [a.service for a in alerts]
        assert "billing-svc" in services
        assert "order-svc" in services

    def test_html_email_description_from_raw(self):
        """When no 'message' description field, _raw should be used."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        # _raw contains the full log line
        assert "dispatcherServlet" in alerts[0].description
        assert "OutOfMemoryError" in alerts[2].description

    def test_aggregated_email_uses_explicit_fields(self):
        """Aggregated query with explicit severity, service, host."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_AGGREGATED_EMAIL)

        assert len(alerts) == 2

        # First row: high severity
        a1 = alerts[0]
        assert a1.severity == "high"
        assert a1.service == "billing-svc"
        assert a1.host == "app-prod-web-2.internal.example.com"

        # Second row: critical severity
        a2 = alerts[1]
        assert a2.severity == "critical"
        assert a2.service == "order-svc"
        assert "OutOfMemoryError" in a2.description

    def test_plain_text_email(self):
        n = EmailNormalizer()
        alerts = n.normalize(PLAIN_TEXT_EMAIL)

        assert len(alerts) == 2
        assert alerts[0].host == "db-01"
        assert alerts[0].name == "Disk Space Warning"

    def test_no_table_creates_single_alert(self):
        """Emails without parseable tables should still create an alert."""
        n = EmailNormalizer()
        alerts = n.normalize(MINIMAL_EMAIL)

        assert len(alerts) == 1
        assert alerts[0].name == "Something Happened"
        assert "alert was triggered" in alerts[0].description

    def test_labels_contain_email_metadata(self):
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        for a in alerts:
            assert a.labels["splunk_email_from"] == "splunk@example.com"
            assert a.labels["splunk_search_name"] == "Production ERROR/FATAL Monitor"

    def test_internal_fields_excluded_from_labels(self):
        """Fields starting with _ should not appear in labels."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        for a in alerts:
            assert "_raw" not in a.labels


class TestEmailWithSplunkCorrelation:
    """Verify that email-ingested alerts will correlate properly."""

    def test_same_service_same_incident(self):
        """Alerts from same service should get same fingerprint base."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        # First two alerts are from billing-svc — same service
        assert alerts[0].service == "billing-svc"
        assert alerts[1].service == "billing-svc"
        # Third alert is from order-svc — different service
        assert alerts[2].service == "order-svc"

    def test_different_hosts_same_service(self):
        """Different hosts with same service should still correlate."""
        n = EmailNormalizer()
        alerts = n.normalize(SPLUNK_HTML_EMAIL)

        # Both from billing-svc on the same host — will dedup
        assert alerts[0].host == alerts[1].host
        # order-svc on different host — separate alert, same incident
        assert alerts[2].host != alerts[0].host
