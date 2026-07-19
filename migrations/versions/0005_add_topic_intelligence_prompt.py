"""add topic intelligence prompt

Revision ID: 0005_add_topic_intelligence_prompt
Revises: 0004_add_ai_framework
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_topic_intelligence_prompt"
down_revision: Union[str, None] = "0004_add_ai_framework"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
                "id": "prompt-topic-intelligence-default",
                "name": "Topic Intelligence Prompt",
                "category": "topic_intelligence",
                "description": "分析主题包内多个用户讨论内容，输出严格 JSON 的主题智能结果。",
                "template": (
                    "你是一名内容策略分析师。你的任务是分析多个用户讨论内容，"
                    "识别用户真正问题、高频痛点、情绪方向、争议点、高价值用户原话、"
                    "内容机会和视频方向建议。不要分析单个帖子，要综合整个主题包。"
                ),
                "variables_json": '["topic_package","contents","comments","metrics"]',
                "version": "1.0",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM studio_prompt_templates WHERE id = 'prompt-topic-intelligence-default'"
    )
