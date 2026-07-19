"""generation queue framework

Revision ID: 0009_generation_queue_framework
Revises: 0008_seed_brainy_default_account
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa


revision: str = "0009_generation_queue_framework"
down_revision: Union[str, None] = "0008_seed_brainy_default_account"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_CREATOR_PERSONA_ID = "persona-default-creator"


def upgrade() -> None:
    now = datetime.now(timezone.utc)

    with op.batch_alter_table("studio_video_projects") as batch:
        batch.alter_column("persona_id", existing_type=sa.String(length=36), nullable=True)
        batch.add_column(sa.Column("creation_mode", sa.String(length=40), nullable=False, server_default="persona"))
    op.create_index("ix_studio_video_projects_creation_mode", "studio_video_projects", ["creation_mode"])

    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.add_column(sa.Column("provider_name", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("provider_task_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("priority", sa.String(length=40), nullable=False, server_default="normal"))
        batch.add_column(sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("max_retry", sa.Integer(), nullable=False, server_default="3"))
        batch.add_column(sa.Column("depends_on_task_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_index("ix_studio_generation_tasks_provider_name", "studio_generation_tasks", ["provider_name"])
    op.create_index("ix_studio_generation_tasks_provider_task_id", "studio_generation_tasks", ["provider_task_id"])
    op.create_index("ix_studio_generation_tasks_priority", "studio_generation_tasks", ["priority"])
    op.create_index("ix_studio_generation_tasks_depends_on_task_id", "studio_generation_tasks", ["depends_on_task_id"])

    op.create_table(
        "studio_generation_pipelines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=120), nullable=False),
        sa.Column("total_tasks", sa.Integer(), nullable=False),
        sa.Column("completed_tasks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_project_id"], ["studio_video_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_generation_pipelines_video_project_id", "studio_generation_pipelines", ["video_project_id"])
    op.create_index("ix_studio_generation_pipelines_status", "studio_generation_pipelines", ["status"])
    op.create_index("ix_studio_generation_pipelines_current_stage", "studio_generation_pipelines", ["current_stage"])

    persona_table = sa.table(
        "studio_personas",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("target_audience", sa.String),
        sa.column("persona_profile_json", sa.Text),
        sa.column("tone_style", sa.String),
        sa.column("language_style", sa.String),
        sa.column("visual_style", sa.String),
        sa.column("voice_style", sa.String),
        sa.column("content_rules_json", sa.Text),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    default_profile = {
        "identity": "general content creator",
        "tone": "neutral",
        "language_style": "general",
        "visual_style": "general",
        "voice_style": "neutral",
    }
    existing = op.get_bind().execute(
        sa.text("SELECT id FROM studio_personas WHERE id = :id"),
        {"id": DEFAULT_CREATOR_PERSONA_ID},
    ).first()
    if not existing:
        op.bulk_insert(
            persona_table,
            [
                {
                    "id": DEFAULT_CREATOR_PERSONA_ID,
                    "name": "Default Creator",
                    "description": "System default general content creator for non-persona production planning.",
                    "target_audience": "General audience",
                    "persona_profile_json": json.dumps(default_profile, ensure_ascii=False, sort_keys=True),
                    "tone_style": "neutral",
                    "language_style": "general",
                    "visual_style": "general",
                    "voice_style": "neutral",
                    "content_rules_json": "{}",
                    "enabled": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def downgrade() -> None:
    op.execute(f"DELETE FROM studio_personas WHERE id = '{DEFAULT_CREATOR_PERSONA_ID}'")

    op.drop_index("ix_studio_generation_pipelines_current_stage", table_name="studio_generation_pipelines")
    op.drop_index("ix_studio_generation_pipelines_status", table_name="studio_generation_pipelines")
    op.drop_index("ix_studio_generation_pipelines_video_project_id", table_name="studio_generation_pipelines")
    op.drop_table("studio_generation_pipelines")

    op.drop_index("ix_studio_generation_tasks_depends_on_task_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_priority", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_provider_task_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_provider_name", table_name="studio_generation_tasks")
    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.drop_column("context_json")
        batch.drop_column("depends_on_task_id")
        batch.drop_column("max_retry")
        batch.drop_column("retry_count")
        batch.drop_column("finished_at")
        batch.drop_column("started_at")
        batch.drop_column("scheduled_at")
        batch.drop_column("priority")
        batch.drop_column("provider_task_id")
        batch.drop_column("provider_name")

    op.drop_index("ix_studio_video_projects_creation_mode", table_name="studio_video_projects")
    with op.batch_alter_table("studio_video_projects") as batch:
        batch.drop_column("creation_mode")
        batch.alter_column("persona_id", existing_type=sa.String(length=36), nullable=False)
