"""Legacy initialization entrypoint.

Database schema changes must be performed through Alembic migrations.
Demo data seeding must be run explicitly through the seed script.
This module must never create or drop database tables.
"""


def init_db() -> None:
    raise RuntimeError(
        "Automatic database initialization is disabled. "
        "Use `alembic upgrade head` to apply schema migrations, "
        "and run the explicit demo seed script when needed."
    )
