from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "ok", "service": "solace"}


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check — verifies dependencies are available."""
    # TODO: Check DB and Redis connectivity
    return {"status": "ready"}
