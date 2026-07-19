"""add topic packages

Revision ID: 0003_add_topic_packages
Revises: 0002_add_atos_push_fields
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_topic_packages"
down_revision: Union[str, None] = "0002_add_atos_push_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_content_items") as batch:
        batch.add_column(sa.Column("review_note", sa.String(length=2000), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "studio_topic_packages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("normalized_title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_angle", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("total_comment_count", sa.Integer(), nullable=False),
        sa.Column("average_source_score", sa.Float(), nullable=True),
        sa.Column("max_source_score", sa.Integer(), nullable=True),
        sa.Column("target_content_type", sa.String(length=60), nullable=True),
        sa.Column("target_platforms_json", sa.Text(), nullable=False),
        sa.Column("operator_note", sa.String(length=2000), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("merged_into_topic_package_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_topic_packages_title", "studio_topic_packages", ["title"])
    op.create_index("ix_studio_topic_packages_normalized_title", "studio_topic_packages", ["normalized_title"])
    op.create_index("ix_studio_topic_packages_status", "studio_topic_packages", ["status"])
    op.create_index("ix_studio_topic_packages_risk_level", "studio_topic_packages", ["risk_level"])
    op.create_index("ix_studio_topic_packages_priority", "studio_topic_packages", ["priority"])
    op.create_index("ix_studio_topic_packages_merged_into_topic_package_id", "studio_topic_packages", ["merged_into_topic_package_id"])

    op.create_table(
        "studio_topic_package_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic_package_id", sa.String(length=36), nullable=False),
        sa.Column("content_item_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["studio_content_items.id"]),
        sa.ForeignKeyConstraint(["topic_package_id"], ["studio_topic_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_package_id", "content_item_id", name="uq_topic_package_content_item"),
    )
    op.create_index("ix_studio_topic_package_items_topic_package_id", "studio_topic_package_items", ["topic_package_id"])
    op.create_index("ix_studio_topic_package_items_content_item_id", "studio_topic_package_items", ["content_item_id"])

    op.create_table(
        "studio_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_audit_events_entity_type", "studio_audit_events", ["entity_type"])
    op.create_index("ix_studio_audit_events_entity_id", "studio_audit_events", ["entity_id"])
    op.create_index("ix_studio_audit_events_action", "studio_audit_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_studio_audit_events_action", table_name="studio_audit_events")
    op.drop_index("ix_studio_audit_events_entity_id", table_name="studio_audit_events")
    op.drop_index("ix_studio_audit_events_entity_type", table_name="studio_audit_events")
    op.drop_table("studio_audit_events")

    op.drop_index("ix_studio_topic_package_items_content_item_id", table_name="studio_topic_package_items")
    op.drop_index("ix_studio_topic_package_items_topic_package_id", table_name="studio_topic_package_items")
    op.drop_table("studio_topic_package_items")

    op.drop_index("ix_studio_topic_packages_merged_into_topic_package_id", table_name="studio_topic_packages")
    op.drop_index("ix_studio_topic_packages_priority", table_name="studio_topic_packages")
    op.drop_index("ix_studio_topic_packages_risk_level", table_name="studio_topic_packages")
    op.drop_index("ix_studio_topic_packages_status", table_name="studio_topic_packages")
    op.drop_index("ix_studio_topic_packages_normalized_title", table_name="studio_topic_packages")
    op.drop_index("ix_studio_topic_packages_title", table_name="studio_topic_packages")
    op.drop_table("studio_topic_packages")

    with op.batch_alter_table("studio_content_items") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("rejected_at")
        batch.drop_column("approved_at")
        batch.drop_column("reviewed_at")
        batch.drop_column("review_note")
