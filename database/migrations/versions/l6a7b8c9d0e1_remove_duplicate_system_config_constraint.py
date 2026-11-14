"""remove duplicate system config uniqueness constraint

Revision ID: l6a7b8c9d0e1
Revises: k5f6a7b8c9d0
"""

from typing import Sequence, Union

from alembic import op


revision: str = "l6a7b8c9d0e1"
down_revision: Union[str, None] = "k5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "system_config_key_key",
        "system_config",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "system_config_key_key",
        "system_config",
        ["key"],
    )
