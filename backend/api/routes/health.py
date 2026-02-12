import logging

from fastapi import APIRouter
from sqlalchemy import text

from backend.config import get_settings
from backend.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

settings = get_settings()


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "ok", "service": "solace"}


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check — verifies dependencies are available."""
    checks: dict[str, str] = {}

    # Check database
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")
        checks["database"] = "unavailable"

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning(f"Redis readiness check failed: {e}")
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())

    if not all_ok:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "checks": checks},
        )

    return {"status": "ready", "checks": checks}
