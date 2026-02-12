import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.integrations import get_normalizer
from backend.schemas import WebhookAcceptedResponse
from backend.services import ingest_alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/{provider}",
    response_model=WebhookAcceptedResponse,
    status_code=202,
    summary="Receive alert webhook",
    description=(
        "Accepts alert payloads from any monitoring source. "
        "The provider path parameter selects the normalizer used to "
        "parse the payload (e.g., 'generic', 'prometheus', 'splunk')."
    ),
)
async def receive_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookAcceptedResponse:
    """Receive and process an alert webhook.

    Flow:
    1. Parse raw JSON body
    2. Select normalizer based on provider
    3. Normalize payload into internal alert format
    4. Run through dedup + ingestion pipeline
    5. Return 202 Accepted immediately

    In the future, step 4 will be offloaded to a background worker
    via Redis/Celery for true async processing under load.
    """
    # Parse raw body
    try:
        payload = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Get the normalizer for this provider
    try:
        normalizer = get_normalizer(provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate the payload
    if not normalizer.validate(payload):
        raise HTTPException(
            status_code=422,
            detail=f"Payload does not match expected schema for provider '{provider}'",
        )

    # Normalize — some providers send batched alerts
    try:
        normalized_alerts = normalizer.normalize(payload)
    except Exception as e:
        logger.error(f"Normalization failed for {provider}: {e}")
        raise HTTPException(status_code=422, detail=f"Failed to normalize payload: {e}")

    # Process each normalized alert through ingestion
    # For batch webhooks (like Prometheus), we process all alerts
    # but return info about the first one for simplicity
    last_alert = None
    last_is_dup = False

    for normalized in normalized_alerts:
        alert, is_duplicate = await ingest_alert(db, normalized)
        last_alert = alert
        last_is_dup = is_duplicate

    if not last_alert:
        raise HTTPException(status_code=422, detail="No alerts could be extracted from payload")

    return WebhookAcceptedResponse(
        status="accepted",
        alert_id=last_alert.id,
        fingerprint=last_alert.fingerprint,
        is_duplicate=last_is_dup,
        duplicate_count=last_alert.duplicate_count,
        incident_id=last_alert.incident_id,
    )
