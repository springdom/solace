import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from backend.api.deps import require_api_key, require_auth
from backend.api.routes import (
    alerts,
    health,
    incidents,
    notifications,
    oncall,
    runbooks,
    silences,
    stats,
    users,
    webhooks,
)
from backend.api.routes import auth as auth_routes
from backend.api.routes import settings as settings_routes
from backend.api.routes.ws import router as ws_router
from backend.config import get_settings
from backend.core.security import hash_password
from backend.database import async_session
from backend.models import User, UserRole

settings = get_settings()

# ─── Logging ─────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ─── Admin Seeding ──────────────────────────────────────


async def seed_default_admin() -> None:
    """Create default admin user if no users exist. Idempotent."""
    async with async_session() as db:
        result = await db.execute(select(func.count(User.id)))
        count = result.scalar() or 0
        if count == 0:
            admin = User(
                email=settings.admin_email,
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
                display_name="Admin",
                role=UserRole.ADMIN,
                must_change_password=False,
            )
            db.add(admin)
            await db.commit()
            logger.info(
                "Default admin account created (username: %s)", settings.admin_username
            )


# ─── Lifespan ───────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Solace (%s)", settings.app_env)
    await seed_default_admin()
    logger.info(
        "API docs available at http://%s:%s/docs", settings.host, settings.port
    )
    yield
    logger.info("Shutting down Solace")


# ─── App ─────────────────────────────────────────────────

app = FastAPI(
    title="Solace",
    description="Open-source alert management and incident response platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_dev else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ──────────────────────────────────────────────

# Health checks at root level (no prefix, no auth — used by k8s probes)
app.include_router(health.router)

# WebSocket — auth is checked inside the handler (WS can't use header deps)
app.include_router(ws_router, prefix=settings.api_prefix)

# Auth routes — no auth required (login must be public)
app.include_router(auth_routes.router, prefix=settings.api_prefix)

# Webhooks — API key only (external systems)
app.include_router(
    webhooks.router, prefix=settings.api_prefix, dependencies=[Depends(require_api_key)]
)

# API routes under /api/v1 — require JWT or API key
api_deps = [Depends(require_auth)]
app.include_router(alerts.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(incidents.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(stats.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(silences.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(notifications.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(settings_routes.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(users.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(oncall.router, prefix=settings.api_prefix, dependencies=api_deps)
app.include_router(runbooks.router, prefix=settings.api_prefix, dependencies=api_deps)
