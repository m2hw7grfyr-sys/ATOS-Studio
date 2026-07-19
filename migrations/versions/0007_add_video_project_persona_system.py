"""add video project persona system

Revision ID: 0007_add_video_project_persona_system
Revises: 0006_upgrade_editorial_briefs
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_video_project_persona_system"
down_revision: Union[str, None] = "0006_upgrade_editorial_briefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "studio_personas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.String(length=500), nullable=False),
        sa.Column("persona_profile_json", sa.Text(), nullable=False),
        sa.Column("tone_style", sa.String(length=200), nullable=False),
        sa.Column("language_style", sa.String(length=200), nullable=False),
        sa.Column("visual_style", sa.String(length=500), nullable=False),
        sa.Column("voice_style", sa.String(length=500), nullable=False),
        sa.Column("content_rules_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_personas_name", "studio_personas", ["name"])
    op.create_index("ix_studio_personas_enabled", "studio_personas", ["enabled"])

    op.create_table(
        "studio_social_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("username", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("persona_id", sa.String(length=36), nullable=True),
        sa.Column("account_notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("publishing_rules_json", sa.Text(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["persona_id"], ["studio_personas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_social_accounts_platform", "studio_social_accounts", ["platform"])
    op.create_index("ix_studio_social_accounts_username", "studio_social_accounts", ["username"])
    op.create_index("ix_studio_social_accounts_persona_id", "studio_social_accounts", ["persona_id"])
    op.create_index("ix_studio_social_accounts_status", "studio_social_accounts", ["status"])

    op.create_table(
        "studio_video_projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic_package_id", sa.String(length=36), nullable=False),
        sa.Column("editorial_brief_id", sa.String(length=36), nullable=False),
        sa.Column("persona_id", sa.String(length=36), nullable=False),
        sa.Column("social_account_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("target_platforms_json", sa.Text(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=40), nullable=False),
        sa.Column("duration_target", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(length=40), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["topic_package_id"], ["studio_topic_packages.id"]),
        sa.ForeignKeyConstraint(["editorial_brief_id"], ["studio_editorial_briefs.id"]),
        sa.ForeignKeyConstraint(["persona_id"], ["studio_personas.id"]),
        sa.ForeignKeyConstraint(["social_account_id"], ["studio_social_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_video_projects_topic_package_id", "studio_video_projects", ["topic_package_id"])
    op.create_index("ix_studio_video_projects_editorial_brief_id", "studio_video_projects", ["editorial_brief_id"])
    op.create_index("ix_studio_video_projects_persona_id", "studio_video_projects", ["persona_id"])
    op.create_index("ix_studio_video_projects_social_account_id", "studio_video_projects", ["social_account_id"])
    op.create_index("ix_studio_video_projects_title", "studio_video_projects", ["title"])
    op.create_index("ix_studio_video_projects_status", "studio_video_projects", ["status"])
    op.create_index("ix_studio_video_projects_priority", "studio_video_projects", ["priority"])

    op.create_table(
        "studio_video_scenes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_project_id", sa.String(length=36), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("voiceover", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False),
        sa.Column("camera_direction", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["video_project_id"], ["studio_video_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_video_scenes_video_project_id", "studio_video_scenes", ["video_project_id"])
    op.create_index("ix_studio_video_scenes_scene_number", "studio_video_scenes", ["scene_number"])
    op.create_index("ix_studio_video_scenes_status", "studio_video_scenes", ["status"])

    op.create_table(
        "studio_generation_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_project_id", sa.String(length=36), nullable=False),
        sa.Column("scene_id", sa.String(length=36), nullable=True),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["video_project_id"], ["studio_video_projects.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["studio_video_scenes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_generation_tasks_video_project_id", "studio_generation_tasks", ["video_project_id"])
    op.create_index("ix_studio_generation_tasks_scene_id", "studio_generation_tasks", ["scene_id"])
    op.create_index("ix_studio_generation_tasks_task_type", "studio_generation_tasks", ["task_type"])
    op.create_index("ix_studio_generation_tasks_status", "studio_generation_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_studio_generation_tasks_status", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_task_type", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_scene_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_video_project_id", table_name="studio_generation_tasks")
    op.drop_table("studio_generation_tasks")

    op.drop_index("ix_studio_video_scenes_status", table_name="studio_video_scenes")
    op.drop_index("ix_studio_video_scenes_scene_number", table_name="studio_video_scenes")
    op.drop_index("ix_studio_video_scenes_video_project_id", table_name="studio_video_scenes")
    op.drop_table("studio_video_scenes")

    op.drop_index("ix_studio_video_projects_priority", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_status", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_title", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_social_account_id", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_persona_id", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_editorial_brief_id", table_name="studio_video_projects")
    op.drop_index("ix_studio_video_projects_topic_package_id", table_name="studio_video_projects")
    op.drop_table("studio_video_projects")

    op.drop_index("ix_studio_social_accounts_status", table_name="studio_social_accounts")
    op.drop_index("ix_studio_social_accounts_persona_id", table_name="studio_social_accounts")
    op.drop_index("ix_studio_social_accounts_username", table_name="studio_social_accounts")
    op.drop_index("ix_studio_social_accounts_platform", table_name="studio_social_accounts")
    op.drop_table("studio_social_accounts")

    op.drop_index("ix_studio_personas_enabled", table_name="studio_personas")
    op.drop_index("ix_studio_personas_name", table_name="studio_personas")
    op.drop_table("studio_personas")
