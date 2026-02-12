import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import alerts, health, incidents, notifications, silences, stats, webhooks
from backend.config import get_settings

settings = get_settings()

# ─── Logging ─────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────

app = FastAPI(
    title="Solace",
    description="Open-source alert management and incident response platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

# Health checks at root level (no prefix)
app.include_router(health.router)

# API routes under /api/v1
app.include_router(webhooks.router, prefix=settings.api_prefix)
app.include_router(alerts.router, prefix=settings.api_prefix)
app.include_router(incidents.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)
app.include_router(silences.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)


# ─── Startup / Shutdown ──────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    logger.info(f"Starting Solace ({settings.app_env})")
    logger.info(f"API docs available at http://{settings.host}:{settings.port}/docs")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Shutting down Solace")
