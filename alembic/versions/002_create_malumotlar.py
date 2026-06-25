"""create malumotlar table

Revision ID: 002_malumotlar
Revises: 001_zaproslar
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_malumotlar"
down_revision: Union[str, None] = "001_zaproslar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "malumotlar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mashina_raqami", sa.String(length=32), nullable=False),
        sa.Column("joriy_lokatsiya", sa.String(length=255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("location_type", sa.String(length=16), nullable=False, server_default="named"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mashina_raqami", name="uq_malumotlar_mashina_raqami"),
    )


def downgrade() -> None:
    op.drop_table("malumotlar")
