"""add_user_lockout_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('last_failed_login', sa.DateTime(), nullable=True))
    op.execute("UPDATE users SET failed_login_attempts = 0 WHERE failed_login_attempts IS NULL")
    op.alter_column('users', 'failed_login_attempts', nullable=False, existing_type=sa.Integer(), server_default='0')


def downgrade() -> None:
    op.drop_column('users', 'last_failed_login')
    op.drop_column('users', 'failed_login_attempts')
