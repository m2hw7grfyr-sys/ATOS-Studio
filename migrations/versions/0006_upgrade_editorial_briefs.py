"""upgrade editorial briefs

Revision ID: 0006_upgrade_editorial_briefs
Revises: 0005_add_topic_intelligence_prompt
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "0006_upgrade_editorial_briefs"
down_revision: Union[str, None] = "0005_add_topic_intelligence_prompt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("studio_editorial_briefs", sa.Column("prompt_template_id", sa.String(length=36), nullable=True))
    op.add_column("studio_editorial_briefs", sa.Column("input_context_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("studio_editorial_briefs", sa.Column("output_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("studio_editorial_briefs", sa.Column("created_by", sa.String(length=120), nullable=True))
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
                "id": "prompt-editorial-short-video-default",
                "name": "Short Video Script Template",
                "category": "editorial",
                "description": "面向 TikTok、Reels、YouTube Shorts 的短视频编导 JSON 模板。",
                "template": (
                    "你是一名短视频内容导演。请基于主题、用户痛点、用户原话、AI分析和内容机会，"
                    "设计一条适合 TikTok、Reels、YouTube Shorts 的短视频编导方案。"
                    "输出必须是严格 JSON。"
                ),
                "variables_json": '["topic_package","topic_intelligence","user_quotes","content_opportunities"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM studio_prompt_templates WHERE id = 'prompt-editorial-short-video-default'")
    op.drop_column("studio_editorial_briefs", "created_by")
    op.drop_column("studio_editorial_briefs", "output_json")
    op.drop_column("studio_editorial_briefs", "input_context_json")
    op.drop_column("studio_editorial_briefs", "prompt_template_id")
