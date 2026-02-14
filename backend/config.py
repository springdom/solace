from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────
    app_name: str = "Solace"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me-to-a-random-secret-key"
    api_key: str = ""

    # ── Database ─────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://solace:solace@localhost:5432/solace"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Redis ────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Alert Processing ─────────────────────────────────
    dedup_window_seconds: int = 300
    correlation_window_seconds: int = 600
    flap_threshold_high: int = 50
    flap_threshold_low: int = 25

    # ── Notifications ─────────────────────────────────────
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_address: str = "solace@localhost"
    notification_cooldown_seconds: int = 300
    solace_dashboard_url: str = "http://localhost:3000"

    # ── Auth ────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = "solace"
    admin_email: str = "admin@solace.local"
    jwt_expire_minutes: int = 480  # 8 hours

    # ── Server ───────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
