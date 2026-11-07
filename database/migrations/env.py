 
from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import create_engine, pool
from alembic import context

# --------------------------------------------------
# ADD BACKEND DIRECTORY TO PYTHON PATH
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

# --------------------------------------------------
# IMPORT DATABASE CONFIGURATION
# --------------------------------------------------

from app.core.config import settings
from app.db.base import Base

# --------------------------------------------------
# IMPORT ALL SQLALCHEMY MODELS
# --------------------------------------------------

import app.models.audit_log
import app.models.case_review
import app.models.evidence
import app.models.owner
import app.models.ownership_history
import app.models.parcel
import app.models.parcel_location_submission
import app.models.risk_prediction
import app.models.role
import app.models.subdivision
import app.models.system_config
import app.models.transaction
import app.models.transaction_status_history
import app.models.user
import app.models.user_session
import app.models.verification_result

# --------------------------------------------------
# ALEMBIC CONFIGURATION
# --------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.database_url


# --------------------------------------------------
# OFFLINE MIGRATIONS
# --------------------------------------------------

def run_migrations_offline():

    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=False,
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------
# ONLINE MIGRATIONS
# --------------------------------------------------

def run_migrations_online():

    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )

    try:
        with connectable.connect() as connection:

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=False,
            )

            with context.begin_transaction():
                context.run_migrations()

    finally:
        connectable.dispose()


# --------------------------------------------------
# EXECUTE MIGRATIONS
# --------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
