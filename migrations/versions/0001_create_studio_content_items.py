"""create studio content items

Revision ID: 0001_create_studio_content_items
Revises:
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_create_studio_content_items"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_content_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_platform", sa.String(length=80), nullable=False),
        sa.Column("atos_post_id", sa.String(length=80), nullable=True),
        sa.Column("source_post_id", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_score", sa.Integer(), nullable=True),
        sa.Column("comment_count", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=40), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("source_snapshot_json", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_hash", name="uq_studio_content_source_hash"),
        sa.UniqueConstraint("source_platform", "source_post_id", name="uq_studio_content_source_post"),
    )
    op.create_index("ix_studio_content_items_atos_post_id", "studio_content_items", ["atos_post_id"])
    op.create_index("ix_studio_content_items_source_hash", "studio_content_items", ["source_hash"])
    op.create_index("ix_studio_content_items_source_platform", "studio_content_items", ["source_platform"])
    op.create_index("ix_studio_content_items_source_post_id", "studio_content_items", ["source_post_id"])
    op.create_index("ix_studio_content_items_status", "studio_content_items", ["status"])
    op.create_index("ix_studio_content_items_source_type", "studio_content_items", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_studio_content_items_source_type", table_name="studio_content_items")
    op.drop_index("ix_studio_content_items_status", table_name="studio_content_items")
    op.drop_index("ix_studio_content_items_source_post_id", table_name="studio_content_items")
    op.drop_index("ix_studio_content_items_source_platform", table_name="studio_content_items")
    op.drop_index("ix_studio_content_items_source_hash", table_name="studio_content_items")
    op.drop_index("ix_studio_content_items_atos_post_id", table_name="studio_content_items")
    op.drop_table("studio_content_items")

