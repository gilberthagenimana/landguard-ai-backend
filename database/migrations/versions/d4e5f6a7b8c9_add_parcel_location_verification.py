"""add parcel location verification workflow

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parcels", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("parcels", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("parcels", sa.Column("boundary_geometry", sa.JSON(), nullable=True))
    op.add_column("parcels", sa.Column("location_data_source", sa.String(length=255), nullable=True))
    op.add_column("parcels", sa.Column("location_verification_status", sa.String(length=40), nullable=False, server_default="NOT_SUBMITTED"))
    op.add_column("parcels", sa.Column("location_verification_metadata", sa.JSON(), nullable=True))
    op.add_column("parcels", sa.Column("location_submitted_by", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("location_submitted_at", sa.DateTime(), nullable=True))
    op.add_column("parcels", sa.Column("location_verified_by", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("location_verified_at", sa.DateTime(), nullable=True))
    op.create_index("ix_parcels_location_verification_status", "parcels", ["location_verification_status"])

    op.create_table(
        "parcel_location_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parcel_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("boundary_geometry", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="PENDING_VERIFICATION"),
        sa.Column("submitted_by", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parcel_location_submissions_id", "parcel_location_submissions", ["id"])
    op.create_index("ix_parcel_location_submissions_parcel_id", "parcel_location_submissions", ["parcel_id"])
    op.create_index("ix_parcel_location_submissions_status", "parcel_location_submissions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_parcel_location_submissions_status", table_name="parcel_location_submissions")
    op.drop_index("ix_parcel_location_submissions_parcel_id", table_name="parcel_location_submissions")
    op.drop_index("ix_parcel_location_submissions_id", table_name="parcel_location_submissions")
    op.drop_table("parcel_location_submissions")
    op.drop_index("ix_parcels_location_verification_status", table_name="parcels")
    for column in (
        "location_verified_at", "location_verified_by", "location_submitted_at",
        "location_submitted_by", "location_verification_metadata",
        "location_verification_status", "location_data_source",
        "boundary_geometry", "longitude", "latitude",
    ):
        op.drop_column("parcels", column)