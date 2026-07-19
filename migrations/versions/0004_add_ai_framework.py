"""add ai framework

Revision ID: 0004_add_ai_framework
Revises: 0003_add_topic_packages
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_ai_framework"
down_revision: Union[str, None] = "0003_add_topic_packages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables_json", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_prompt_templates_name", "studio_prompt_templates", ["name"])
    op.create_index("ix_studio_prompt_templates_category", "studio_prompt_templates", ["category"])
    op.create_index("ix_studio_prompt_templates_enabled", "studio_prompt_templates", ["enabled"])

    op.create_table(
        "studio_ai_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("input_snapshot", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_ai_jobs_job_type", "studio_ai_jobs", ["job_type"])
    op.create_index("ix_studio_ai_jobs_entity_type", "studio_ai_jobs", ["entity_type"])
    op.create_index("ix_studio_ai_jobs_entity_id", "studio_ai_jobs", ["entity_id"])
    op.create_index("ix_studio_ai_jobs_status", "studio_ai_jobs", ["status"])

    op.create_table(
        "studio_ai_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic_package_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_type", sa.String(length=80), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["topic_package_id"], ["studio_topic_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_ai_analyses_topic_package_id", "studio_ai_analyses", ["topic_package_id"])
    op.create_index("ix_studio_ai_analyses_analysis_type", "studio_ai_analyses", ["analysis_type"])

    op.create_table(
        "studio_editorial_briefs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic_package_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["topic_package_id"], ["studio_topic_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_editorial_briefs_topic_package_id", "studio_editorial_briefs", ["topic_package_id"])
    op.create_index("ix_studio_editorial_briefs_status", "studio_editorial_briefs", ["status"])

    now = datetime.now(timezone.utc)
    prompt_table = sa.table(
        "studio_prompt_templates",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.String),
        sa.column("template", sa.Text),
        sa.column("variables_json", sa.Text),
        sa.column("version", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        prompt_table,
        [
            {
                "id": "prompt-analysis-default",
                "name": "内容摘要模板",
                "category": "analysis",
                "description": "总结主题包的核心问题、主要观点和内容价值。",
                "template": "请基于主题包来源内容，输出 JSON：core_issue, main_points, source_summary。",
                "variables_json": '["topic_title","sources"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "prompt-audience-default",
                "name": "用户痛点分析模板",
                "category": "audience",
                "description": "提取目标用户、典型痛点和表达方式。",
                "template": "请分析用户痛点，输出 JSON：audience, pain_points, user_language。",
                "variables_json": '["topic_title","sources"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "prompt-comments-default",
                "name": "评论洞察模板",
                "category": "comments",
                "description": "分析评论与来源中的高频表达、情绪和争议点。",
                "template": "请分析评论洞察，输出 JSON：frequent_phrases, sentiment, objections。",
                "variables_json": '["topic_title","sources"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "prompt-video-angle-default",
                "name": "视频方向分析模板",
                "category": "video_angle",
                "description": "提取适合短视频的切入角度和 Hook 建议。",
                "template": "请分析视频方向，输出 JSON：recommended_angle, target_viewer, hook_ideas。",
                "variables_json": '["topic_title","sources","audience"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_studio_editorial_briefs_status", table_name="studio_editorial_briefs")
    op.drop_index("ix_studio_editorial_briefs_topic_package_id", table_name="studio_editorial_briefs")
    op.drop_table("studio_editorial_briefs")

    op.drop_index("ix_studio_ai_analyses_analysis_type", table_name="studio_ai_analyses")
    op.drop_index("ix_studio_ai_analyses_topic_package_id", table_name="studio_ai_analyses")
    op.drop_table("studio_ai_analyses")

    op.drop_index("ix_studio_ai_jobs_status", table_name="studio_ai_jobs")
    op.drop_index("ix_studio_ai_jobs_entity_id", table_name="studio_ai_jobs")
    op.drop_index("ix_studio_ai_jobs_entity_type", table_name="studio_ai_jobs")
    op.drop_index("ix_studio_ai_jobs_job_type", table_name="studio_ai_jobs")
    op.drop_table("studio_ai_jobs")

    op.drop_index("ix_studio_prompt_templates_enabled", table_name="studio_prompt_templates")
    op.drop_index("ix_studio_prompt_templates_category", table_name="studio_prompt_templates")
    op.drop_index("ix_studio_prompt_templates_name", table_name="studio_prompt_templates")
    op.drop_table("studio_prompt_templates")
