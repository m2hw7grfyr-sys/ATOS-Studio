"""add atos push fields

Revision ID: 0002_add_atos_push_fields
Revises: 0001_create_studio_content_items
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_atos_push_fields"
down_revision: Union[str, None] = "0001_create_studio_content_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_content_items") as batch:
        batch.add_column(sa.Column("requested_content_type", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("target_platforms_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("operator_note", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("last_pushed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("push_count", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("studio_content_items") as batch:
        batch.alter_column("target_platforms_json", server_default=None)
        batch.alter_column("push_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("studio_content_items") as batch:
        batch.drop_column("push_count")
        batch.drop_column("last_pushed_at")
        batch.drop_column("operator_note")
        batch.drop_column("target_platforms_json")
        batch.drop_column("requested_content_type")
