"""sync_landguard_models

Revision ID: e3a4b0224f65
Revises: i3d4e5f6a7b8

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3a4b0224f65"
down_revision: Union[str, None] = "i3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only the genuinely-missing schema object remains here.
    # Earlier migrations in the chain already created:
    #   - parcel_location_submissions (d4e5f6a7b8c9)
    #   - user_sessions           (c2d3e4f5a6b7)
    #   - evidence                 (c3d4e5f6a7b8)
    #   - evidence_review_history (c3d4e5f6a7b8)
    #   - parcel location columns (d4e5f6a7b8c9)
    #   - transaction archive cols (f8a9b0c1d2e3)
    # This migration therefore only adds the missing FK on case_reviews.created_by.

    op.create_foreign_key(
        "fk_case_reviews_created_by_users",
        "case_reviews",
        "users",
        ["created_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_case_reviews_created_by_users",
        "case_reviews",
        type_="foreignkey",
    )
