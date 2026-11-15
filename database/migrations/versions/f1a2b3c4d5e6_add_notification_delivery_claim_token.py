"""add notification delivery claim token

Revision ID: f1a2b3c4d5e6
Revises: 67e5b838de13
Create Date: 2026-11-15

This migration is intentionally not applied by the development task.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "67e5b838de13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("claim_token", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_notification_deliveries_claim_token",
        "notification_deliveries",
        ["claim_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_claim_token",
        table_name="notification_deliveries",
    )
    op.drop_column("notification_deliveries", "claim_token")
