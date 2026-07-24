"""add local generation engine registry

Revision ID: 0015_add_local_generation_engine_registry
Revises: 0014_add_studio_job_review_fields
Create Date: 2026-07-25
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa


revision: str = "0015_add_local_generation_engine_registry"
down_revision: Union[str, None] = "0014_add_studio_job_review_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_MODEL_ID = "model-comfyui-default-image"
DEFAULT_PRESET_ID = "preset-image-scene-default"
FAST_PRESET_ID = "preset-image-scene-fast"
WORKFLOW_ID = "workflow-comfyui-basic-image"


def upgrade() -> None:
    with op.batch_alter_table("studio_generation_workflows") as batch:
        batch.add_column(sa.Column("workflow_path", sa.String(length=1000), nullable=False, server_default=""))

    with op.batch_alter_table("studio_model_capabilities") as batch:
        batch.add_column(sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""))
        batch.add_column(sa.Column("engine_id", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("capability", sa.String(length=80), nullable=False, server_default=""))
        batch.add_column(sa.Column("model_identifier", sa.String(length=500), nullable=False, server_default=""))
        batch.add_column(sa.Column("workflow_path", sa.String(length=1000), nullable=False, server_default=""))
        batch.add_column(sa.Column("checkpoint_path", sa.String(length=1000), nullable=False, server_default=""))
        batch.add_column(sa.Column("vae_path", sa.String(length=1000), nullable=False, server_default=""))
        batch.add_column(sa.Column("lora_paths_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
        batch.add_column(sa.Column("estimated_vram_gb", sa.Float(), nullable=True))
        batch.add_column(sa.Column("supported_widths_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("supported_heights_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("supported_durations_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("supported_fps_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("supported_aspect_ratios_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("default_parameters_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("validation_rules_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_index("ix_studio_model_capabilities_engine_id", "studio_model_capabilities", ["engine_id"])
    op.create_index("ix_studio_model_capabilities_capability", "studio_model_capabilities", ["capability"])
    op.create_index("ix_studio_model_capabilities_enabled", "studio_model_capabilities", ["enabled"])
    op.create_index("ix_studio_model_capabilities_is_default", "studio_model_capabilities", ["is_default"])
    op.create_index("ix_studio_model_capabilities_priority", "studio_model_capabilities", ["priority"])

    op.create_table(
        "studio_generation_presets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("engine_id", sa.String(length=120), nullable=False),
        sa.Column("model_profile_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_profile_id", sa.String(length=36), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("fallback_preset_id", sa.String(length=36), nullable=True),
        sa.Column("remark", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fallback_preset_id"], ["studio_generation_presets.id"]),
        sa.ForeignKeyConstraint(["model_profile_id"], ["studio_model_capabilities.id"]),
        sa.ForeignKeyConstraint(["workflow_profile_id"], ["studio_generation_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_generation_presets_name", "studio_generation_presets", ["name"])
    op.create_index("ix_studio_generation_presets_capability", "studio_generation_presets", ["capability"])
    op.create_index("ix_studio_generation_presets_engine_id", "studio_generation_presets", ["engine_id"])
    op.create_index("ix_studio_generation_presets_model_profile_id", "studio_generation_presets", ["model_profile_id"])
    op.create_index("ix_studio_generation_presets_workflow_profile_id", "studio_generation_presets", ["workflow_profile_id"])
    op.create_index("ix_studio_generation_presets_enabled", "studio_generation_presets", ["enabled"])
    op.create_index("ix_studio_generation_presets_is_default", "studio_generation_presets", ["is_default"])
    op.create_index("ix_studio_generation_presets_priority", "studio_generation_presets", ["priority"])
    op.create_index("ix_studio_generation_presets_fallback_preset_id", "studio_generation_presets", ["fallback_preset_id"])

    op.create_table(
        "studio_generation_config_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("generation_task_id", sa.String(length=36), nullable=True),
        sa.Column("video_project_id", sa.String(length=36), nullable=True),
        sa.Column("scene_id", sa.String(length=36), nullable=True),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("engine_id", sa.String(length=120), nullable=False),
        sa.Column("preset_id", sa.String(length=36), nullable=True),
        sa.Column("model_profile_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_profile_id", sa.String(length=36), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("configuration_version", sa.String(length=40), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_from_preset_id", sa.String(length=36), nullable=True),
        sa.Column("fallback_to_preset_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fallback_from_preset_id"], ["studio_generation_presets.id"]),
        sa.ForeignKeyConstraint(["fallback_to_preset_id"], ["studio_generation_presets.id"]),
        sa.ForeignKeyConstraint(["generation_task_id"], ["studio_generation_tasks.id"]),
        sa.ForeignKeyConstraint(["model_profile_id"], ["studio_model_capabilities.id"]),
        sa.ForeignKeyConstraint(["preset_id"], ["studio_generation_presets.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["studio_video_scenes.id"]),
        sa.ForeignKeyConstraint(["video_project_id"], ["studio_video_projects.id"]),
        sa.ForeignKeyConstraint(["workflow_profile_id"], ["studio_generation_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_generation_config_snapshots_generation_task_id", "studio_generation_config_snapshots", ["generation_task_id"])
    op.create_index("ix_studio_generation_config_snapshots_video_project_id", "studio_generation_config_snapshots", ["video_project_id"])
    op.create_index("ix_studio_generation_config_snapshots_scene_id", "studio_generation_config_snapshots", ["scene_id"])
    op.create_index("ix_studio_generation_config_snapshots_capability", "studio_generation_config_snapshots", ["capability"])
    op.create_index("ix_studio_generation_config_snapshots_engine_id", "studio_generation_config_snapshots", ["engine_id"])
    op.create_index("ix_studio_generation_config_snapshots_preset_id", "studio_generation_config_snapshots", ["preset_id"])
    op.create_index("ix_studio_generation_config_snapshots_model_profile_id", "studio_generation_config_snapshots", ["model_profile_id"])
    op.create_index("ix_studio_generation_config_snapshots_workflow_profile_id", "studio_generation_config_snapshots", ["workflow_profile_id"])
    op.create_index("ix_studio_generation_config_snapshots_fallback_used", "studio_generation_config_snapshots", ["fallback_used"])

    op.create_table(
        "studio_preflight_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("generation_task_id", sa.String(length=36), nullable=True),
        sa.Column("video_project_id", sa.String(length=36), nullable=True),
        sa.Column("scene_id", sa.String(length=36), nullable=True),
        sa.Column("engine_id", sa.String(length=120), nullable=False),
        sa.Column("preset_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("checks_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generation_task_id"], ["studio_generation_tasks.id"]),
        sa.ForeignKeyConstraint(["preset_id"], ["studio_generation_presets.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["studio_video_scenes.id"]),
        sa.ForeignKeyConstraint(["video_project_id"], ["studio_video_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_preflight_results_generation_task_id", "studio_preflight_results", ["generation_task_id"])
    op.create_index("ix_studio_preflight_results_video_project_id", "studio_preflight_results", ["video_project_id"])
    op.create_index("ix_studio_preflight_results_scene_id", "studio_preflight_results", ["scene_id"])
    op.create_index("ix_studio_preflight_results_engine_id", "studio_preflight_results", ["engine_id"])
    op.create_index("ix_studio_preflight_results_preset_id", "studio_preflight_results", ["preset_id"])
    op.create_index("ix_studio_preflight_results_status", "studio_preflight_results", ["status"])
    op.create_index("ix_studio_preflight_results_checked_at", "studio_preflight_results", ["checked_at"])

    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.add_column(sa.Column("preset_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("engine_id", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("model_profile_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("workflow_profile_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("configuration_version", sa.String(length=40), nullable=False, server_default="legacy"))
        batch.add_column(sa.Column("configuration_snapshot_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("preflight_result_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_generation_tasks_preset_id", "studio_generation_presets", ["preset_id"], ["id"])
        batch.create_foreign_key("fk_generation_tasks_model_profile_id", "studio_model_capabilities", ["model_profile_id"], ["id"])
        batch.create_foreign_key("fk_generation_tasks_workflow_profile_id", "studio_generation_workflows", ["workflow_profile_id"], ["id"])
    op.create_index("ix_studio_generation_tasks_preset_id", "studio_generation_tasks", ["preset_id"])
    op.create_index("ix_studio_generation_tasks_engine_id", "studio_generation_tasks", ["engine_id"])
    op.create_index("ix_studio_generation_tasks_model_profile_id", "studio_generation_tasks", ["model_profile_id"])
    op.create_index("ix_studio_generation_tasks_workflow_profile_id", "studio_generation_tasks", ["workflow_profile_id"])
    op.create_index("ix_studio_generation_tasks_fallback_used", "studio_generation_tasks", ["fallback_used"])

    now = datetime.now(timezone.utc)
    model_table = sa.table(
        "studio_model_capabilities",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("provider", sa.String),
        sa.column("engine_id", sa.String),
        sa.column("capability", sa.String),
        sa.column("model_type", sa.String),
        sa.column("model_identifier", sa.String),
        sa.column("workflow_path", sa.String),
        sa.column("checkpoint_path", sa.String),
        sa.column("vae_path", sa.String),
        sa.column("lora_paths_json", sa.Text),
        sa.column("enabled", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("priority", sa.Integer),
        sa.column("estimated_vram_gb", sa.Float),
        sa.column("supported_widths_json", sa.Text),
        sa.column("supported_heights_json", sa.Text),
        sa.column("supported_durations_json", sa.Text),
        sa.column("supported_fps_json", sa.Text),
        sa.column("supported_aspect_ratios_json", sa.Text),
        sa.column("default_parameters_json", sa.Text),
        sa.column("validation_rules_json", sa.Text),
        sa.column("version", sa.String),
        sa.column("status", sa.String),
        sa.column("metadata_json", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        model_table,
        [
            {
                "id": DEFAULT_MODEL_ID,
                "name": "ComfyUI Default Image",
                "display_name": "ComfyUI Default Image",
                "provider": "comfyui",
                "engine_id": "comfyui",
                "capability": "image",
                "model_type": "image",
                "model_identifier": "comfyui-workflow-default",
                "workflow_path": "",
                "checkpoint_path": "",
                "vae_path": "",
                "lora_paths_json": "[]",
                "enabled": True,
                "is_default": True,
                "priority": 100,
                "estimated_vram_gb": None,
                "supported_widths_json": json.dumps([512, 768, 1024]),
                "supported_heights_json": json.dumps([512, 768, 1024]),
                "supported_durations_json": "[]",
                "supported_fps_json": "[]",
                "supported_aspect_ratios_json": json.dumps(["1:1", "9:16", "16:9"]),
                "default_parameters_json": json.dumps({"width": 768, "height": 1024}),
                "validation_rules_json": "{}",
                "version": "v1",
                "status": "available",
                "metadata_json": "{}",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    preset_table = sa.table(
        "studio_generation_presets",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("capability", sa.String),
        sa.column("engine_id", sa.String),
        sa.column("model_profile_id", sa.String),
        sa.column("workflow_profile_id", sa.String),
        sa.column("parameters_json", sa.Text),
        sa.column("timeout_seconds", sa.Integer),
        sa.column("max_attempts", sa.Integer),
        sa.column("enabled", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("priority", sa.Integer),
        sa.column("fallback_preset_id", sa.String),
        sa.column("remark", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        preset_table,
        [
            {
                "id": DEFAULT_PRESET_ID,
                "name": "image_scene_default",
                "display_name": "Image Scene Default",
                "capability": "image",
                "engine_id": "comfyui",
                "model_profile_id": DEFAULT_MODEL_ID,
                "workflow_profile_id": WORKFLOW_ID,
                "parameters_json": json.dumps({"width": 768, "height": 1024, "aspect_ratio": "9:16"}),
                "timeout_seconds": 120,
                "max_attempts": 1,
                "enabled": True,
                "is_default": True,
                "priority": 100,
                "fallback_preset_id": FAST_PRESET_ID,
                "remark": "Default local image preset for scene generation.",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": FAST_PRESET_ID,
                "name": "image_scene_fast",
                "display_name": "Image Scene Fast",
                "capability": "image",
                "engine_id": "comfyui",
                "model_profile_id": DEFAULT_MODEL_ID,
                "workflow_profile_id": WORKFLOW_ID,
                "parameters_json": json.dumps({"width": 512, "height": 768, "aspect_ratio": "9:16", "quality": "fast"}),
                "timeout_seconds": 90,
                "max_attempts": 1,
                "enabled": True,
                "is_default": False,
                "priority": 200,
                "fallback_preset_id": None,
                "remark": "Lower-resource fallback image preset.",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_studio_generation_tasks_fallback_used", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_workflow_profile_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_model_profile_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_engine_id", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_preset_id", table_name="studio_generation_tasks")
    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.drop_constraint("fk_generation_tasks_workflow_profile_id", type_="foreignkey")
        batch.drop_constraint("fk_generation_tasks_model_profile_id", type_="foreignkey")
        batch.drop_constraint("fk_generation_tasks_preset_id", type_="foreignkey")
        batch.drop_column("fallback_used")
        batch.drop_column("preflight_result_json")
        batch.drop_column("configuration_snapshot_json")
        batch.drop_column("configuration_version")
        batch.drop_column("workflow_profile_id")
        batch.drop_column("model_profile_id")
        batch.drop_column("engine_id")
        batch.drop_column("preset_id")

    op.drop_index("ix_studio_preflight_results_checked_at", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_status", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_preset_id", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_engine_id", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_scene_id", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_video_project_id", table_name="studio_preflight_results")
    op.drop_index("ix_studio_preflight_results_generation_task_id", table_name="studio_preflight_results")
    op.drop_table("studio_preflight_results")

    op.drop_index("ix_studio_generation_config_snapshots_fallback_used", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_workflow_profile_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_model_profile_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_preset_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_engine_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_capability", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_scene_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_video_project_id", table_name="studio_generation_config_snapshots")
    op.drop_index("ix_studio_generation_config_snapshots_generation_task_id", table_name="studio_generation_config_snapshots")
    op.drop_table("studio_generation_config_snapshots")

    op.drop_index("ix_studio_generation_presets_fallback_preset_id", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_priority", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_is_default", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_enabled", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_workflow_profile_id", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_model_profile_id", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_engine_id", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_capability", table_name="studio_generation_presets")
    op.drop_index("ix_studio_generation_presets_name", table_name="studio_generation_presets")
    op.drop_table("studio_generation_presets")

    op.drop_index("ix_studio_model_capabilities_priority", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_is_default", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_enabled", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_capability", table_name="studio_model_capabilities")
    op.drop_index("ix_studio_model_capabilities_engine_id", table_name="studio_model_capabilities")
    with op.batch_alter_table("studio_model_capabilities") as batch:
        batch.drop_column("validation_rules_json")
        batch.drop_column("default_parameters_json")
        batch.drop_column("supported_aspect_ratios_json")
        batch.drop_column("supported_fps_json")
        batch.drop_column("supported_durations_json")
        batch.drop_column("supported_heights_json")
        batch.drop_column("supported_widths_json")
        batch.drop_column("estimated_vram_gb")
        batch.drop_column("priority")
        batch.drop_column("is_default")
        batch.drop_column("enabled")
        batch.drop_column("lora_paths_json")
        batch.drop_column("vae_path")
        batch.drop_column("checkpoint_path")
        batch.drop_column("workflow_path")
        batch.drop_column("model_identifier")
        batch.drop_column("capability")
        batch.drop_column("engine_id")
        batch.drop_column("display_name")

    with op.batch_alter_table("studio_generation_workflows") as batch:
        batch.drop_column("workflow_path")
