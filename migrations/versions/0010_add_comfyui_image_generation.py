"""add comfyui image generation

Revision ID: 0010_add_comfyui_image_generation
Revises: 0009_generation_queue_framework
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa


revision: str = "0010_add_comfyui_image_generation"
down_revision: Union[str, None] = "0009_generation_queue_framework"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BASIC_WORKFLOW_ID = "workflow-comfyui-basic-image"


def upgrade() -> None:
    op.create_table(
        "studio_generation_workflows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("workflow_type", sa.String(length=80), nullable=False),
        sa.Column("workflow_json", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_generation_workflows_name", "studio_generation_workflows", ["name"])
    op.create_index("ix_studio_generation_workflows_provider", "studio_generation_workflows", ["provider"])
    op.create_index("ix_studio_generation_workflows_workflow_type", "studio_generation_workflows", ["workflow_type"])
    op.create_index("ix_studio_generation_workflows_version", "studio_generation_workflows", ["version"])
    op.create_index("ix_studio_generation_workflows_enabled", "studio_generation_workflows", ["enabled"])

    op.create_table(
        "studio_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("generation_task_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generation_task_id"], ["studio_generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_assets_asset_type", "studio_assets", ["asset_type"])
    op.create_index("ix_studio_assets_provider", "studio_assets", ["provider"])
    op.create_index("ix_studio_assets_generation_task_id", "studio_assets", ["generation_task_id"])

    now = datetime.now(timezone.utc)
    workflow_table = sa.table(
        "studio_generation_workflows",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("provider", sa.String),
        sa.column("workflow_type", sa.String),
        sa.column("workflow_json", sa.Text),
        sa.column("version", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    workflow = {
        "description": "Replace this placeholder with a real ComfyUI workflow API JSON.",
        "prompt_variable": "{{visual_prompt}}",
        "negative_prompt": "low quality, blurry, distorted",
        "expected_output": "image",
    }
    op.bulk_insert(
        workflow_table,
        [
            {
                "id": BASIC_WORKFLOW_ID,
                "name": "basic_image_generation",
                "provider": "comfyui",
                "workflow_type": "image_generation",
                "workflow_json": json.dumps(workflow, ensure_ascii=False, sort_keys=True),
                "version": "v1",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_studio_assets_generation_task_id", table_name="studio_assets")
    op.drop_index("ix_studio_assets_provider", table_name="studio_assets")
    op.drop_index("ix_studio_assets_asset_type", table_name="studio_assets")
    op.drop_table("studio_assets")

    op.drop_index("ix_studio_generation_workflows_enabled", table_name="studio_generation_workflows")
    op.drop_index("ix_studio_generation_workflows_version", table_name="studio_generation_workflows")
    op.drop_index("ix_studio_generation_workflows_workflow_type", table_name="studio_generation_workflows")
    op.drop_index("ix_studio_generation_workflows_provider", table_name="studio_generation_workflows")
    op.drop_index("ix_studio_generation_workflows_name", table_name="studio_generation_workflows")
    op.drop_table("studio_generation_workflows")
