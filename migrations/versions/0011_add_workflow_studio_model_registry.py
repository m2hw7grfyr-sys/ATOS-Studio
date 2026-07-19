"""add workflow studio model registry

Revision ID: 0011_add_workflow_studio_model_registry
Revises: 0010_add_comfyui_image_generation
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_add_workflow_studio_model_registry"
down_revision: Union[str, None] = "0010_add_comfyui_image_generation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_generation_workflows") as batch:
        batch.add_column(sa.Column("description", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"))
        batch.add_column(sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("required_models_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("test_result_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("created_by", sa.String(length=120), nullable=False, server_default="operator"))
    op.create_index("ix_studio_generation_workflows_status", "studio_generation_workflows", ["status"])
    op.create_index("ix_studio_generation_workflows_created_by", "studio_generation_workflows", ["created_by"])

    op.create_table(
        "studio_model_capabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_model_capabilities_name", "studio_model_capabilities", ["name"])
    op.create_index("ix_studio_model_capabilities_provider", "studio_model_capabilities", ["provider"])
    op.create_index("ix_studio_model_capabilities_model_type", "studio_model_capabilities", ["model_type"])
    op.create_index("ix_studio_model_capabilities_status", "studio_model_capabilities", ["status"])


def downgrade() -> None:
    op.drop_index("ix_studio_model_capabilities_status", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_model_type", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_provider", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_name", table_name="studio_model_capabilities")
    op.drop_table("studio_model_capabilities")

    op.drop_index("ix_studio_generation_workflows_created_by", table_name="studio_generation_workflows")
    op.drop_index("ix_studio_generation_workflows_status", table_name="studio_generation_workflows")
    with op.batch_alter_table("studio_generation_workflows") as batch:
        batch.drop_column("created_by")
        batch.drop_column("last_tested_at")
        batch.drop_column("test_result_json")
        batch.drop_column("required_models_json")
        batch.drop_column("tags_json")
        batch.drop_column("status")
        batch.drop_column("description")
