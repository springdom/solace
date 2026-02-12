"""Email ingestion normalizer for Splunk alert emails.

Splunk alert emails contain an HTML table with search results.
Unlike the webhook (which only sends the first result row), emails
include ALL result rows — making email ingestion actually richer.

Typical Splunk alert email:
- Subject: "Splunk Alert: <search_name>"
- Body: HTML with a <table> containing search results
- Each <tr> is one result row with columns matching the SPL query

Example email subject:
  "Splunk Alert: Production ERROR/FATAL Monitor"

Example email body (simplified):
  <html>
  <body>
    <p>Alert triggered: Production ERROR/FATAL Monitor</p>
    <table>
      <tr><th>host</th><th>source</th><th>message</th><th>_raw</th></tr>
      <tr><td>web-01</td><td>/var/log/myapp/myapp.log</td>
          <td>ERROR</td><td>2026-02-12 04:10:57 ERROR ...</td></tr>
      <tr><td>web-02</td><td>/var/log/myapp/myapp.log</td>
          <td>FATAL</td><td>2026-02-12 04:11:02 FATAL ...</td></tr>
    </table>
  </body>
  </html>

This normalizer:
1. Extracts the search name from the email subject
2. Parses the HTML table into rows
3. Uses the same field-extraction heuristics as the Splunk webhook normalizer
4. Creates one NormalizedAlert per result row
"""

import re
from html.parser import HTMLParser

from backend.integrations import BaseNormalizer, NormalizedAlert
from backend.integrations.splunk import (
    DESCRIPTION_FIELD_KEYS,
    ENV_FIELD_KEYS,
    HOST_FIELD_KEYS,
    SERVICE_FIELD_KEYS,
    _build_labels,
    _extract_from_result,
    _extract_severity,
)


def _extract_search_name(subject: str) -> str:
    """Extract the search/alert name from a Splunk email subject.

    Common formats:
    - "Splunk Alert: High CPU Usage Alert"
    - "Splunk Alert - High CPU Usage Alert"
    - "[Splunk] High CPU Usage Alert"
    - "High CPU Usage Alert"  (custom subject)
    """
    # Try "Splunk Alert: <name>" or "Splunk Alert - <name>"
    match = re.match(r"Splunk\s+Alert[\s:–\-]+(.+)", subject, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try "[Splunk] <name>"
    match = re.match(r"\[Splunk\]\s*(.+)", subject, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fall back to the full subject
    return subject.strip() or "Splunk Email Alert"


class _TableParser(HTMLParser):
    """Simple HTML parser that extracts table data into rows of dicts.

    Handles nested tags within <td> cells (e.g., <a>, <span>, <b>)
    by collecting all text content within each cell.
    """

    def __init__(self):
        super().__init__()
        self.tables: list[list[dict[str, str]]] = []
        self._headers: list[str] = []
        self._rows: list[dict[str, str]] = []
        self._current_row: list[str] = []
        self._in_table = False
        self._in_thead = False
        self._in_th = False
        self._in_td = False
        self._in_tr = False
        self._cell_text = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag == "table":
            self._in_table = True
            self._headers = []
            self._rows = []
        elif tag == "thead":
            self._in_thead = True
        elif tag == "tr":
            self._in_tr = True
            self._current_row = []
        elif tag == "th":
            self._in_th = True
            self._cell_text = ""
        elif tag == "td":
            self._in_td = True
            self._cell_text = ""

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._rows:
                self.tables.append(self._rows)
            self._in_table = False
        elif tag == "thead":
            self._in_thead = False
        elif tag == "th":
            self._in_th = False
            self._current_row.append(self._cell_text.strip())
        elif tag == "td":
            self._in_td = False
            self._current_row.append(self._cell_text.strip())
        elif tag == "tr":
            self._in_tr = False
            if self._in_table:
                if not self._headers and self._current_row:
                    # First row with content — check if it's headers
                    # (Splunk sometimes puts headers in <td> instead of <th>)
                    if self._in_thead or all(
                        not cell.replace(".", "").replace("-", "").replace("_", "").isdigit()
                        for cell in self._current_row
                        if cell
                    ):
                        self._headers = self._current_row
                    else:
                        self._headers = self._current_row
                elif self._current_row and self._headers:
                    # Build dict from headers + row values
                    row_dict = {}
                    for i, header in enumerate(self._headers):
                        if i < len(self._current_row):
                            row_dict[header] = self._current_row[i]
                    if any(v.strip() for v in row_dict.values()):
                        self._rows.append(row_dict)

    def handle_data(self, data: str) -> None:
        if self._in_th or self._in_td:
            self._cell_text += data


def parse_html_tables(html: str) -> list[list[dict[str, str]]]:
    """Parse all HTML tables into lists of row dicts."""
    parser = _TableParser()
    parser.feed(html)
    return parser.tables


def parse_plain_text_table(text: str) -> list[dict[str, str]]:
    """Attempt to parse a plain-text table from Splunk email.

    Splunk plain-text emails sometimes use tab or pipe delimiters.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return []

    # Try tab-delimited
    headers = lines[0].split("\t")
    if len(headers) > 1:
        rows = []
        for line in lines[1:]:
            values = line.split("\t")
            if len(values) >= len(headers):
                row = {headers[i]: values[i].strip() for i in range(len(headers))}
                rows.append(row)
        if rows:
            return rows

    # Try pipe-delimited (some Splunk setups use | table output)
    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    if len(headers) > 1:
        rows = []
        for line in lines[1:]:
            if line.startswith("-") or line.startswith("="):
                continue  # separator line
            values = [v.strip() for v in line.split("|") if v.strip()]
            if len(values) >= len(headers):
                row = {headers[i]: values[i] for i in range(len(headers))}
                rows.append(row)
        if rows:
            return rows

    return []


class EmailNormalizer(BaseNormalizer):
    """Normalizes Splunk alert emails into NormalizedAlerts.

    Accepts a JSON payload with email fields:
    {
        "subject": "Splunk Alert: Production ERROR/FATAL Monitor",
        "body_html": "<html>...<table>...</table>...</html>",
        "body_text": "host\\tsource\\tmessage\\n...",  // optional fallback
        "from": "splunk@example.com",                  // optional metadata
        "to": "alerts@company.com"                     // optional metadata
    }

    Produces one NormalizedAlert per result row in the email table.
    """

    def validate(self, payload: dict) -> bool:
        """Check that this looks like an email payload with parseable content."""
        if "subject" not in payload:
            return False
        if "body_html" not in payload and "body_text" not in payload:
            return False
        return True

    def normalize(self, payload: dict) -> list[NormalizedAlert]:
        """Parse email content and create alerts from table rows."""
        subject = payload.get("subject", "")
        body_html = payload.get("body_html", "")
        body_text = payload.get("body_text", "")
        sender = payload.get("from", "")

        search_name = _extract_search_name(subject)

        # Try HTML tables first, fall back to plain text
        rows: list[dict[str, str]] = []
        if body_html:
            tables = parse_html_tables(body_html)
            if tables:
                # Use the largest table (most likely the results table)
                rows = max(tables, key=len)

        if not rows and body_text:
            rows = parse_plain_text_table(body_text)

        # If no table rows found, create a single alert from the email itself
        if not rows:
            return [
                NormalizedAlert(
                    name=search_name,
                    source="splunk",
                    severity="warning",
                    status="firing",
                    description=body_text[:500] if body_text else subject,
                    labels={
                        "splunk_email_from": sender,
                        "splunk_email_subject": subject,
                    },
                    annotations={},
                    raw_payload=payload,
                )
            ]

        # Create one alert per result row
        normalized = []
        for row in rows:
            # Reuse the Splunk webhook field extraction logic
            severity = _extract_severity(row)
            host = _extract_from_result(row, HOST_FIELD_KEYS)
            service = _extract_from_result(row, SERVICE_FIELD_KEYS)
            environment = _extract_from_result(row, ENV_FIELD_KEYS)
            description = _extract_from_result(row, DESCRIPTION_FIELD_KEYS)

            # If description is very short (e.g., just "ERROR" or "FATAL" from
            # a rex extraction), prefer _raw or latest_error for more context
            if description and len(description) <= 10:
                longer = (
                    row.get("latest_error")
                    or row.get("_raw", "")[:500]
                )
                if longer and len(longer) > len(description):
                    description = longer

            # If no description from known fields, use _raw
            if not description and "_raw" in row:
                description = row["_raw"][:500]

            # Track extracted keys for clean labels
            extracted_keys: set[str] = set()
            for key_list in [
                HOST_FIELD_KEYS, SERVICE_FIELD_KEYS,
                ENV_FIELD_KEYS, DESCRIPTION_FIELD_KEYS,
            ]:
                for key in key_list:
                    if key in row:
                        extracted_keys.add(key)
            # Also exclude severity-related keys
            from backend.integrations.splunk import SEVERITY_FIELD_KEYS
            for key in SEVERITY_FIELD_KEYS:
                if key in row:
                    extracted_keys.add(key)
            # Exclude _raw since we used it for description
            extracted_keys.add("_raw")

            labels = _build_labels(row, extracted_keys)
            labels["splunk_email_from"] = sender
            labels["splunk_search_name"] = search_name

            # Try to derive service from the source (log path)
            if not service:
                source_path = row.get("source", "")
                if source_path:
                    # Extract app name from paths like /opt/app/APP_NAME/log/...
                    match = re.search(r"/([^/]+)/logs?/", source_path)
                    if match:
                        service = match.group(1)

            normalized.append(
                NormalizedAlert(
                    name=search_name,
                    source="splunk",
                    severity=severity,
                    status="firing",
                    description=description,
                    service=service,
                    environment=environment,
                    host=host,
                    labels=labels,
                    annotations={},
                    raw_payload=row,
                )
            )

        return normalized
