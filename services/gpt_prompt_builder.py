from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.ai import StudioAIAnalysis, StudioEditorialBrief
from models.production import StudioPersona
from repositories.content_items import parse_json, stable_json
from schemas.editorial_brief import validate_editorial_brief_json
from services.ai_service import active_prompt_for_category
from services.topic_packages import serialize_topic_package
from models.topic_package import StudioTopicPackage


EDITORIAL_PROMPT_CATEGORY = "editorial"
EDITORIAL_BRIEF_STATUSES = {"draft", "reviewing", "approved", "archived", "ready_for_video"}


def latest_topic_intelligence(db: Session, topic_package_id: str) -> StudioAIAnalysis:
    row = db.scalar(
        select(StudioAIAnalysis)
        .where(
            StudioAIAnalysis.topic_package_id == topic_package_id,
            StudioAIAnalysis.analysis_type == "topic_intelligence",
        )
        .order_by(StudioAIAnalysis.updated_at.desc(), StudioAIAnalysis.created_at.desc())
        .limit(1)
    )
    if not row:
        raise HTTPException(status_code=422, detail="缺少主题智能分析结果，请先运行 topic_intelligence_analysis")
    return row


def serialize_prompt_persona(row: StudioPersona) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "target_audience": row.target_audience,
        "persona_profile": parse_json(row.persona_profile_json, {}),
        "tone_style": row.tone_style,
        "language_style": row.language_style,
        "visual_style": row.visual_style,
        "voice_style": row.voice_style,
        "content_rules": parse_json(row.content_rules_json, {}),
    }


def editorial_context(db: Session, topic_package_id: str, persona_id: Optional[str] = None) -> dict[str, Any]:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    topic_intelligence = latest_topic_intelligence(db, topic_package_id)
    persona = None
    if persona_id:
        persona = db.get(StudioPersona, persona_id)
        if not persona or not persona.enabled:
            raise HTTPException(status_code=422, detail="enabled persona not found")
    payload = {
        "topic_package": serialize_topic_package(db, package, include_items=True),
        "topic_intelligence": parse_json(topic_intelligence.result_json, {}),
        "topic_intelligence_analysis_id": topic_intelligence.id,
        "topic_intelligence_provider": topic_intelligence.provider,
        "topic_intelligence_model": topic_intelligence.model,
    }
    if persona:
        payload["persona"] = serialize_prompt_persona(persona)
    return payload


def build_editorial_prompt(db: Session, topic_package_id: str, persona_id: Optional[str] = None) -> dict[str, Any]:
    context = editorial_context(db, topic_package_id, persona_id)
    template = active_prompt_for_category(db, EDITORIAL_PROMPT_CATEGORY)
    required_output = {
        "title": "",
        "hook": "",
        "target_audience": "",
        "script": "",
        "scenes": [
            {
                "scene_number": 1,
                "duration": 5,
                "visual_prompt": "",
                "voiceover": "",
                "subtitle": "",
                "camera_direction": "",
            }
        ],
        "caption": "",
        "hashtags": [],
    }
    persona = context.get("persona") or {}
    persona_block = ""
    if persona:
        profile = persona.get("persona_profile") or {}
        rules = persona.get("content_rules") or {}
        persona_block = (
            "\n\nCreate content for this persona:\n"
            f"Name: {persona.get('name')}\n"
            f"Identity: {profile.get('identity') or persona.get('description')}\n"
            f"Tone: {profile.get('tone') or persona.get('tone_style')}\n"
            f"Audience: {persona.get('target_audience')}\n"
            f"Language: {profile.get('language') or persona.get('language_style')}\n"
            f"Style: {profile.get('style') or persona.get('visual_style')}\n"
            f"Voice: {persona.get('voice_style')}\n"
            f"Avoid: {json.dumps(profile.get('avoid') or rules.get('avoid') or [], ensure_ascii=False)}"
        )
    prompt = (
        f"{template.template}\n\n"
        f"{persona_block}\n\n"
        "请只输出严格 JSON，不要输出 Markdown，不要添加解释。\n"
        f"输出结构必须符合：\n{json.dumps(required_output, ensure_ascii=False, indent=2)}\n\n"
        f"素材上下文 JSON：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return {
        "prompt": prompt,
        "prompt_template_id": template.id,
        "prompt_version": template.version,
        "input_context": context,
    }


def next_brief_version(db: Session, topic_package_id: str) -> str:
    count = db.scalar(
        select(func.count(StudioEditorialBrief.id)).where(StudioEditorialBrief.topic_package_id == topic_package_id)
    ) or 0
    return str(int(count) + 1)


def save_editorial_output(
    db: Session,
    topic_package_id: str,
    prompt_snapshot: str,
    output_json: str,
    prompt_template_id: Optional[str] = None,
    input_context: Optional[dict[str, Any]] = None,
    created_by: str = "operator",
    status: str = "draft",
) -> StudioEditorialBrief:
    if status not in EDITORIAL_BRIEF_STATUSES:
        raise HTTPException(status_code=422, detail="invalid editorial brief status")
    parsed_output = validate_editorial_brief_json(output_json)
    if input_context is None or prompt_template_id is None:
        built = build_editorial_prompt(db, topic_package_id)
        prompt_template_id = prompt_template_id or built["prompt_template_id"]
        input_context = input_context or built["input_context"]
        if not prompt_snapshot.strip():
            prompt_snapshot = built["prompt"]
    if not prompt_snapshot.strip():
        built = build_editorial_prompt(db, topic_package_id)
        prompt_snapshot = built["prompt"]
        prompt_template_id = prompt_template_id or built["prompt_template_id"]
        input_context = input_context or built["input_context"]
    row = StudioEditorialBrief(
        topic_package_id=topic_package_id,
        version=next_brief_version(db, topic_package_id),
        prompt_template_id=prompt_template_id,
        prompt_snapshot=prompt_snapshot,
        input_context_json=stable_json(input_context or {}),
        input_json=stable_json(parsed_output),
        output_json=stable_json(parsed_output),
        status=status,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def serialize_editorial_brief(row: StudioEditorialBrief) -> dict[str, Any]:
    output = parse_json(row.output_json, {})
    if not output:
        output = parse_json(row.input_json, {})
    return {
        "id": row.id,
        "topic_package_id": row.topic_package_id,
        "version": row.version,
        "status": row.status,
        "prompt_template_id": row.prompt_template_id,
        "prompt_snapshot": row.prompt_snapshot,
        "input_context": parse_json(row.input_context_json, {}),
        "output": output,
        "input": output,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def update_editorial_brief_status(db: Session, brief_id: str, status: str) -> StudioEditorialBrief:
    if status not in EDITORIAL_BRIEF_STATUSES:
        raise HTTPException(status_code=422, detail="invalid editorial brief status")
    row = db.get(StudioEditorialBrief, brief_id)
    if not row:
        raise HTTPException(status_code=404, detail="editorial brief not found")
    row.status = status
    db.flush()
    return row
