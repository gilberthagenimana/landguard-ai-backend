"""allow nullable parcel UPI and remove redundant unique index

Revision ID: j4e5f6a7b8c9
Revises: e3a4b0224f65
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j4e5f6a7b8c9"
down_revision: Union[str, None] = "e3a4b0224f65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "parcels",
        "upi",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.drop_index("ix_parcels_upi", table_name="parcels")


def downgrade() -> None:
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT count(*) FROM parcels WHERE upi IS NULL")
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot downgrade parcel UPI while NULL values exist."
        )

    op.create_index(
        "ix_parcels_upi",
        "parcels",
        ["upi"],
        unique=True,
    )
    op.alter_column(
        "parcels",
        "upi",
        existing_type=sa.String(length=100),
        nullable=False,
    )
