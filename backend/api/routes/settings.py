from fastapi import APIRouter

from backend.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", summary="Get application settings")
async def get_app_settings() -> dict:
    """Return read-only application configuration."""
    s = get_settings()
    return {
        "app_name": s.app_name,
        "app_env": s.app_env,
        "dedup_window_seconds": s.dedup_window_seconds,
        "correlation_window_seconds": s.correlation_window_seconds,
        "notification_cooldown_seconds": s.notification_cooldown_seconds,
        "solace_dashboard_url": s.solace_dashboard_url,
    }
