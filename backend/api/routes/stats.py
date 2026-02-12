"""Dashboard stats API route."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services import get_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", summary="Dashboard statistics")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get alert/incident counts, MTTA, and MTTR."""
    return await get_stats(db)
