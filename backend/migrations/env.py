from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from backend.config import get_settings
from backend.database import Base

# Import all models so Alembic can detect them
from backend.models import Alert, AlertNote, EscalationPolicy, Incident, IncidentEvent, Integration, NotificationChannel, NotificationLog, OnCallOverride, OnCallSchedule, RunbookRule, ServiceEscalationMapping, SilenceWindow, User  # noqa: F401

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
