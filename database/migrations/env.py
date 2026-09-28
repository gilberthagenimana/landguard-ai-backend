from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import settings
from app.db.base import Base
import app.models.audit_log  # noqa: F401
import app.models.case_review  # noqa: F401
import app.models.owner  # noqa: F401
import app.models.ownership_history  # noqa: F401
import app.models.parcel  # noqa: F401
import app.models.risk_prediction  # noqa: F401
import app.models.role  # noqa: F401
import app.models.transaction  # noqa: F401
import app.models.user  # noqa: F401
import app.models.verification_result  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
