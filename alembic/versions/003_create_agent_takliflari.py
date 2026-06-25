"""create agent_takliflari table

Revision ID: 003_agent_takliflari
Revises: 002_malumotlar
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_agent_takliflari"
down_revision: Union[str, None] = "002_malumotlar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_takliflari",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zapros_id", sa.Integer(), nullable=False),
        sa.Column("mashina_id", sa.Integer(), nullable=False),
        sa.Column("zapros_yaratilgan_vaqti", sa.DateTime(), nullable=False),
        sa.Column("agent_taklif_bergan_vaqti", sa.DateTime(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["zapros_id"], ["zaproslar.id"], name="fk_takliflari_zapros"),
        sa.ForeignKeyConstraint(["mashina_id"], ["malumotlar.id"], name="fk_takliflari_mashina"),
    )
    op.create_index("ix_agent_takliflari_zapros_id", "agent_takliflari", ["zapros_id"])
    op.create_index("ix_agent_takliflari_mashina_id", "agent_takliflari", ["mashina_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_takliflari_mashina_id", table_name="agent_takliflari")
    op.drop_index("ix_agent_takliflari_zapros_id", table_name="agent_takliflari")
    op.drop_table("agent_takliflari")
