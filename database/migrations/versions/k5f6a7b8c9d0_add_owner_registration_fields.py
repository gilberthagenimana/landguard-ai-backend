"""add owner registration fields and identifier indexes

Revision ID: k5f6a7b8c9d0
Revises: j4e5f6a7b8c9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k5f6a7b8c9d0"
down_revision: Union[str, None] = "j4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "owners",
        sa.Column(
            "owner_type",
            sa.String(length=20),
            nullable=False,
            server_default="INDIVIDUAL",
        ),
    )
    op.add_column(
        "owners",
        sa.Column("organization_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "owners",
        sa.Column("registration_number", sa.String(length=100), nullable=True),
    )
    op.create_check_constraint(
        "ck_owners_owner_type",
        "owners",
        "owner_type IN ('INDIVIDUAL', 'ORGANIZATION')",
    )
    op.create_index(
        "ix_owners_identification_number_unique",
        "owners",
        ["identification_number"],
        unique=True,
    )
    op.create_index(
        "ix_owners_registration_number_unique",
        "owners",
        ["registration_number"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    populated = bind.execute(
        sa.text(
            "SELECT count(*) FROM owners "
            "WHERE organization_name IS NOT NULL OR registration_number IS NOT NULL "
            "OR owner_type <> 'INDIVIDUAL'"
        )
    ).scalar_one()
    if populated:
        raise RuntimeError(
            "Cannot downgrade owner registration fields while they contain data."
        )

    op.drop_index("ix_owners_registration_number_unique", table_name="owners")
    op.drop_index("ix_owners_identification_number_unique", table_name="owners")
    op.drop_constraint("ck_owners_owner_type", "owners", type_="check")
    op.drop_column("owners", "registration_number")
    op.drop_column("owners", "organization_name")
    op.drop_column("owners", "owner_type")
