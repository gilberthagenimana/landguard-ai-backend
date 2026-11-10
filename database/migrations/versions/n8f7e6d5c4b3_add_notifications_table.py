"""add_notifications_table

Revision ID: n8f7e6d5c4b3
Revises: l6a7b8c9d0e1
Create Date: 2026-11-10 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n8f7e6d5c4b3"
down_revision: Union[str, None] = "l6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("related_parcel_upi", sa.String(length=100), nullable=True),
        sa.Column("related_transaction_code", sa.String(length=50), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f('ix_notifications_recipient_user_id'), 'notifications', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_notifications_event_type'), 'notifications', ['event_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_event_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_user_id'), table_name='notifications')
    op.drop_table('notifications')
