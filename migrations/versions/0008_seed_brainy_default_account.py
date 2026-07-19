"""seed brainy default account

Revision ID: 0008_seed_brainy_default_account
Revises: 0007_add_video_project_persona_system
Create Date: 2026-07-19
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa


revision: str = "0008_seed_brainy_default_account"
down_revision: Union[str, None] = "0007_add_video_project_persona_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BRAINY_PERSONA_ID = "persona-brainy-default"
BRAINY_ACCOUNT_ID = "social-brainy-tiredbrainclub"


def upgrade() -> None:
    now = datetime.now(timezone.utc)
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
    account_table = sa.table(
        "studio_social_accounts",
        sa.column("id", sa.String),
        sa.column("platform", sa.String),
        sa.column("username", sa.String),
        sa.column("display_name", sa.String),
        sa.column("persona_id", sa.String),
        sa.column("account_notes", sa.Text),
        sa.column("status", sa.String),
        sa.column("publishing_rules_json", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    persona_profile = {
        "identity": "college student / ordinary office worker / exhausted overthinker",
        "display_identity": "深夜想法的陪伴者 / 你的精神内耗代言人",
        "age_range": "18-25",
        "gender": "gender-neutral",
        "personality": ["敏感", "内耗", "容易疲惫", "内心柔软善良"],
        "state": "常年累，常年想太多，努力在混乱中寻找秩序",
        "tags": ["ADHD", "焦虑", "拖延", "高敏感", "深夜EMO"],
        "tone": "tired, gentle, self-aware, lightly humorous",
        "language": "short empathetic Chinese-English friendly captions",
        "style": "personal storytelling and late-night inner monologue",
        "signature_visuals": {
            "hoodie": "oversized charcoal hoodie",
            "eyes": "sleepy and slightly empty but kind",
            "expression": "tired, anxious, thinking, mildly happy",
            "palette": ["#3E3E3E", "#6B7280", "#A5A7AD", "#DCD6C9", "#EDEAE3"],
        },
        "recommended_scenes": ["late night room", "on the way", "daily corner"],
        "account_name_ideas": [
            "@TiredBrainClub",
            "@BurnoutDiaries",
            "@LateNightThoughts",
            "@MentallyExhausted",
            "@ADHDiary_",
            "@OverthinkingClub",
        ],
        "avoid": ["medical claims", "diagnosis", "dosage advice", "crisis intervention claims"],
    }
    content_rules = {
        "allowed": ["ADHD daily life", "mental exhaustion", "late-night thoughts", "self-acceptance"],
        "avoid": ["medical claims", "diagnosis", "dosage advice", "promising cures"],
        "voice_rules": [
            "sound like a tired but safe friend",
            "validate feelings before offering ideas",
            "keep captions short and emotionally specific",
        ],
        "core_keywords": ["疲惫感", "安全感", "陪伴感", "治愈感", "共鸣感"],
    }
    publishing_rules = {
        "default_role": "Brainy 小脑瓜",
        "primary_content": ["ADHD", "焦虑", "拖延", "高敏感", "深夜EMO"],
        "target_platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
        "default_hashtags": ["ADHD", "overthinking", "burnout", "latenightthoughts"],
        "manual_review_required": True,
    }
    op.bulk_insert(
        persona_table,
        [
            {
                "id": BRAINY_PERSONA_ID,
                "name": "Brainy（小脑瓜）",
                "description": "深夜想法的陪伴者 / 你的精神内耗代言人",
                "target_audience": "ADHD、焦虑、拖延、高敏感、深夜EMO，以及所有感到疲惫的人",
                "persona_profile_json": json.dumps(persona_profile, ensure_ascii=False, sort_keys=True),
                "tone_style": "敏感、疲惫、温柔、共情，带一点自嘲式幽默",
                "language_style": "短句、低能量、像深夜朋友聊天；适合中文为主，可混少量英文短语",
                "visual_style": "经典灰黑 hoodie、标志性黑眼圈、极简表情、灰米色低饱和调色、深夜房间/通勤/日常角落",
                "voice_style": "低声、柔软、安全感、陪伴感，不说教",
                "content_rules_json": json.dumps(content_rules, ensure_ascii=False, sort_keys=True),
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        account_table,
        [
            {
                "id": BRAINY_ACCOUNT_ID,
                "platform": "tiktok",
                "username": "TiredBrainClub",
                "display_name": "Brainy 小脑瓜",
                "persona_id": BRAINY_PERSONA_ID,
                "account_notes": "默认账号；基于 Brainy 角色设定，用于深夜想法、ADHD日常、精神内耗和自我接纳类短视频。",
                "status": "active",
                "publishing_rules_json": json.dumps(publishing_rules, ensure_ascii=False, sort_keys=True),
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM studio_social_accounts WHERE id = '{BRAINY_ACCOUNT_ID}'")
    op.execute(f"DELETE FROM studio_personas WHERE id = '{BRAINY_PERSONA_ID}'")
