"""add_upi_and_new_tables

Revision ID: a1b2c3d4e5f6
Revises: 4d979c0060d0
Create Date: 2026-10-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4d979c0060d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add UPI column to parcels
    op.add_column('parcels', sa.Column('upi', sa.String(length=100), nullable=True))
    op.create_unique_constraint('uq_parcels_upi', 'parcels', ['upi'])
    op.create_index(op.f('ix_parcels_upi'), 'parcels', ['upi'], unique=True)

    # Add has_pending_transaction column to parcels
    op.add_column('parcels', sa.Column('has_pending_transaction', sa.Boolean(), nullable=True, server_default='0'))

    # Update existing parcels with UPI values
    op.execute("UPDATE parcels SET upi = 'DEMO-UPI-LEGACY-' || id WHERE upi IS NULL")
    op.execute("UPDATE parcels SET has_pending_transaction = false WHERE has_pending_transaction IS NULL")

    # Make UPI non-nullable after populating
    op.alter_column('parcels', 'upi', nullable=False, existing_type=sa.String(length=100))
    op.alter_column('parcels', 'has_pending_transaction', nullable=False, existing_type=sa.Boolean(), server_default='0')

    # Create subdivisions table
    op.create_table('subdivisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subdivision_code', sa.String(length=50), nullable=False),
        sa.Column('parent_parcel_id', sa.Integer(), nullable=False),
        sa.Column('new_parcel_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('area_ha', sa.Float(), nullable=False),
        sa.Column('supporting_reference', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['new_parcel_id'], ['parcels.id'], ),
        sa.ForeignKeyConstraint(['parent_parcel_id'], ['parcels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subdivisions_id'), 'subdivisions', ['id'], unique=False)
    op.create_index(op.f('ix_subdivisions_new_parcel_id'), 'subdivisions', ['new_parcel_id'], unique=False)
    op.create_index(op.f('ix_subdivisions_parent_parcel_id'), 'subdivisions', ['parent_parcel_id'], unique=False)
    op.create_index(op.f('ix_subdivisions_status'), 'subdivisions', ['status'], unique=False)
    op.create_index(op.f('ix_subdivisions_subdivision_code'), 'subdivisions', ['subdivision_code'], unique=True)

    # Create transaction_status_history table
    op.create_table('transaction_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('previous_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_status_history_id'), 'transaction_status_history', ['id'], unique=False)
    op.create_index(op.f('ix_transaction_status_history_transaction_id'), 'transaction_status_history', ['transaction_id'], unique=False)

    # Create system_config table
    op.create_table('system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index(op.f('ix_system_config_id'), 'system_config', ['id'], unique=False)
    op.create_index(op.f('ix_system_config_key'), 'system_config', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_config_key'), table_name='system_config')
    op.drop_index(op.f('ix_system_config_id'), table_name='system_config')
    op.drop_table('system_config')

    op.drop_index(op.f('ix_transaction_status_history_transaction_id'), table_name='transaction_status_history')
    op.drop_index(op.f('ix_transaction_status_history_id'), table_name='transaction_status_history')
    op.drop_table('transaction_status_history')

    op.drop_index(op.f('ix_subdivisions_subdivision_code'), table_name='subdivisions')
    op.drop_index(op.f('ix_subdivisions_status'), table_name='subdivisions')
    op.drop_index(op.f('ix_subdivisions_parent_parcel_id'), table_name='subdivisions')
    op.drop_index(op.f('ix_subdivisions_new_parcel_id'), table_name='subdivisions')
    op.drop_index(op.f('ix_subdivisions_id'), table_name='subdivisions')
    op.drop_table('subdivisions')

    op.alter_column('parcels', 'has_pending_transaction', nullable=True, existing_type=sa.Boolean())
    op.alter_column('parcels', 'upi', nullable=True, existing_type=sa.String(length=100))
    op.drop_index(op.f('ix_parcels_upi'), table_name='parcels')
    op.drop_constraint('uq_parcels_upi', 'parcels', type_='unique')
    op.drop_column('parcels', 'has_pending_transaction')
    op.drop_column('parcels', 'upi')
