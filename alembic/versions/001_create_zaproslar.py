"""create zaproslar table

Revision ID: 001_zaproslar
Revises:
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_zaproslar"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zaproslar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("yuk_ortish_joyi", sa.String(length=255), nullable=False),
        sa.Column("yuk_tushirish_joyi", sa.String(length=255), nullable=False),
        sa.Column("yuklash_sanasi", sa.Date(), nullable=False),
        sa.Column("ortish_lat", sa.Float(), nullable=True),
        sa.Column("ortish_lng", sa.Float(), nullable=True),
        sa.Column("location_type", sa.String(length=16), nullable=False, server_default="named"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("zaproslar")
