FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY forwarder.py .

ENV IMAP_HOST="" \
    IMAP_PORT="993" \
    IMAP_USER="" \
    IMAP_PASSWORD="" \
    IMAP_USE_SSL="true" \
    IMAP_FOLDER="INBOX" \
    SUBJECT_PATTERN="Splunk Alert" \
    SOLACE_URL="http://localhost:8000" \
    SOLACE_API_KEY="" \
    POLL_INTERVAL="60" \
    MARK_AS_READ="true" \
    MOVE_TO_FOLDER=""

CMD ["python", "forwarder.py"]
