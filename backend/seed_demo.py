import os

from sqlalchemy.engine import make_url

from app.core.config import settings

database_url = make_url(settings.database_url)

if settings.app_env.lower() != "development":
    raise SystemExit("BLOCKED: Demo seeding requires development environment.")

if os.getenv("ALLOW_DEMO_SEEDING", "").lower() != "true":
    raise SystemExit("BLOCKED: Set ALLOW_DEMO_SEEDING=true to explicitly enable demo seeding.")

allowed_hosts = {"localhost", "127.0.0.1", "::1"}
is_sqlite = database_url.get_backend_name() == "sqlite"
is_local_postgres = database_url.host in allowed_hosts

if not (is_sqlite or is_local_postgres):
    raise SystemExit(
        f"BLOCKED: Demo seeding is not allowed on remote database host: {database_url.host}"
    )

from app.db.seed import seed_demo_data
from app.db.session import SessionLocal

db = SessionLocal()

try:
    seed_demo_data(db)
    print("Demo seed completed successfully.")
finally:
    db.close()
