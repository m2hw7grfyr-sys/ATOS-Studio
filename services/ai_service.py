from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import get_settings
from models.ai import StudioAIAnalysis, StudioAIJob, StudioEditorialBrief, StudioPromptTemplate
from models.content_item import utc_now
from models.topic_package import StudioTopicPackage
from repositories.content_items import parse_json, stable_json
from services.ai.providers.local_llm import LocalLLMProvider
from services.ai.providers.openai_provider import OpenAIProvider
from services.ai.providers.llm_provider import LLMGeneration
from services.topic_packages import serialize_topic_package


JOB_TO_ANALYSIS = {
    "topic_summary": ("analysis", "summary"),
    "pain_point_analysis": ("audience", "pain_points"),
    "comment_analysis": ("comments", "comments"),
    "video_angle_analysis": ("video_angle", "video_angle"),
}
VALID_AI_JOB_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}
VALID_AI_JOB_TYPES = set(JOB_TO_ANALYSIS)
VALID_EDITORIAL_BRIEF_STATUSES = {"draft", "reviewed", "approved"}


def get_ai_provider(provider_name: Optional[str] = None):
    settings = get_settings()
    provider = (provider_name or settings.ai_provider or "local").lower()
    if provider == "openai":
        return OpenAIProvider(settings)
    return LocalLLMProvider(settings)


def ai_health_payload() -> dict:
    settings = get_settings()
    provider = get_ai_provider(settings.ai_provider)
    health = provider.health_check()
    return {
        "provider": health.provider,
        "status": health.status,
        "model": health.model,
        "message": health.message,
    }


def serialize_prompt_template(row: StudioPromptTemplate) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "template": row.template,
        "variables": parse_json(row.variables_json, []),
        "version": row.version,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_ai_job(row: StudioAIJob) -> dict:
    return {
        "id": row.id,
        "job_type": row.job_type,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "status": row.status,
        "provider": row.provider,
        "model": row.model,
        "input_snapshot": parse_json(row.input_snapshot, {}),
        "output": parse_json(row.output_json, {}),
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def serialize_ai_analysis(row: StudioAIAnalysis) -> dict:
    return {
        "id": row.id,
        "topic_package_id": row.topic_package_id,
        "analysis_type": row.analysis_type,
        "result": parse_json(row.result_json, {}),
        "provider": row.provider,
        "model": row.model,
        "prompt_version": row.prompt_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_prompt_templates(db: Session, category: Optional[str] = None, enabled: Optional[bool] = None) -> list[dict]:
    statement = select(StudioPromptTemplate)
    if category:
        statement = statement.where(StudioPromptTemplate.category == category)
    if enabled is not None:
        statement = statement.where(StudioPromptTemplate.enabled == enabled)
    rows = db.scalars(statement.order_by(StudioPromptTemplate.category, StudioPromptTemplate.name)).all()
    return [serialize_prompt_template(row) for row in rows]


def create_prompt_template(db: Session, payload: dict) -> StudioPromptTemplate:
    row = StudioPromptTemplate(
        name=str(payload.get("name") or "").strip(),
        category=str(payload.get("category") or "").strip(),
        description=str(payload.get("description") or ""),
        template=str(payload.get("template") or "").strip(),
        variables_json=stable_json(payload.get("variables") or []),
        version=str(payload.get("version") or "1.0"),
        enabled=bool(payload.get("enabled", True)),
    )
    if not row.name or not row.category or not row.template:
        raise HTTPException(status_code=422, detail="name, category, and template are required")
    db.add(row)
    db.flush()
    return row


def active_prompt_for_category(db: Session, category: str) -> StudioPromptTemplate:
    row = db.scalar(
        select(StudioPromptTemplate)
        .where(StudioPromptTemplate.category == category, StudioPromptTemplate.enabled.is_(True))
        .order_by(StudioPromptTemplate.updated_at.desc())
        .limit(1)
    )
    if not row:
        raise HTTPException(status_code=422, detail=f"enabled prompt template not found for category: {category}")
    return row


def topic_input_snapshot(db: Session, topic_package_id: str) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    return serialize_topic_package(db, package, include_items=True)


def render_prompt(template: StudioPromptTemplate, snapshot: dict) -> str:
    sources = []
    for item in snapshot.get("items", []):
        content = item.get("content_item") or {}
        sources.append(
            {
                "title": content.get("title"),
                "body": content.get("body"),
                "platform": content.get("source_platform"),
                "score": content.get("source_score"),
                "comments": content.get("comment_count"),
                "risk": content.get("risk_level"),
            }
        )
    context = {
        "topic_title": snapshot.get("title"),
        "summary": snapshot.get("summary"),
        "content_angle": snapshot.get("content_angle"),
        "sources": sources,
    }
    return f"{template.template}\n\n主题包上下文 JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def parse_generation(text: str, fallback_type: str) -> dict:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass
    return {"analysis_type": fallback_type, "text": text}


def create_ai_job(db: Session, topic_package_id: str, job_type: str) -> StudioAIJob:
    if job_type not in VALID_AI_JOB_TYPES:
        raise HTTPException(status_code=422, detail="invalid ai job type")
    snapshot = topic_input_snapshot(db, topic_package_id)
    job = StudioAIJob(
        job_type=job_type,
        entity_type="topic_package",
        entity_id=topic_package_id,
        status="pending",
        input_snapshot=stable_json(snapshot),
    )
    db.add(job)
    db.flush()
    return job


def create_default_topic_ai_jobs(db: Session, topic_package_id: str) -> list[StudioAIJob]:
    return [create_ai_job(db, topic_package_id, job_type) for job_type in JOB_TO_ANALYSIS]


def run_ai_job(db: Session, job_id: str, provider_override=None) -> StudioAIJob:
    job = db.get(StudioAIJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ai job not found")
    if job.status == "cancelled":
        raise HTTPException(status_code=422, detail="cancelled job cannot run")
    category, analysis_type = JOB_TO_ANALYSIS.get(job.job_type, ("analysis", "summary"))
    template = active_prompt_for_category(db, category)
    snapshot = parse_json(job.input_snapshot, {})
    prompt = render_prompt(template, snapshot)
    provider = provider_override or get_ai_provider()
    job.status = "running"
    job.started_at = utc_now()
    job.provider = getattr(provider, "provider_name", "unknown")
    job.model = provider.get_model_info().get("model")
    db.flush()
    try:
        generation: LLMGeneration = provider.generate(prompt)
        result = parse_generation(generation.text, analysis_type)
        job.status = "completed"
        job.output_json = stable_json(result)
        job.provider = generation.provider
        job.model = generation.model
        job.error_message = None
        analysis = StudioAIAnalysis(
            topic_package_id=job.entity_id,
            analysis_type=analysis_type,
            result_json=stable_json(result),
            provider=generation.provider,
            model=generation.model,
            prompt_version=template.version,
        )
        db.add(analysis)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:1000]
    finally:
        job.finished_at = utc_now()
        db.flush()
    return job


def topic_ai_jobs(db: Session, topic_package_id: str) -> list[dict]:
    rows = db.scalars(
        select(StudioAIJob)
        .where(StudioAIJob.entity_type == "topic_package", StudioAIJob.entity_id == topic_package_id)
        .order_by(StudioAIJob.created_at.desc())
    ).all()
    return [serialize_ai_job(row) for row in rows]


def topic_ai_analyses(db: Session, topic_package_id: str) -> list[dict]:
    rows = db.scalars(
        select(StudioAIAnalysis)
        .where(StudioAIAnalysis.topic_package_id == topic_package_id)
        .order_by(StudioAIAnalysis.updated_at.desc())
    ).all()
    return [serialize_ai_analysis(row) for row in rows]


def generate_gpt_director_prompt(db: Session, topic_package_id: str) -> str:
    snapshot = topic_input_snapshot(db, topic_package_id)
    analyses = topic_ai_analyses(db, topic_package_id)
    return (
        "你是短视频编导。请基于以下主题包和 AI Insights，输出内容 brief JSON，"
        "包括 hook、目标用户、核心痛点、三段结构、素材引用和风险注意事项。\n\n"
        f"主题包：{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"AI Insights：{json.dumps(analyses, ensure_ascii=False, indent=2)}"
    )


def save_editorial_brief(db: Session, topic_package_id: str, prompt_snapshot: str, input_json: str) -> StudioEditorialBrief:
    topic_input_snapshot(db, topic_package_id)
    try:
        parsed = json.loads(input_json or "{}")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="editorial brief input must be valid JSON") from exc
    row = StudioEditorialBrief(
        topic_package_id=topic_package_id,
        version="1.0",
        prompt_snapshot=prompt_snapshot,
        input_json=stable_json(parsed),
        status="draft",
    )
    db.add(row)
    db.flush()
    return row


def serialize_editorial_brief(row: StudioEditorialBrief) -> dict:
    return {
        "id": row.id,
        "topic_package_id": row.topic_package_id,
        "version": row.version,
        "prompt_snapshot": row.prompt_snapshot,
        "input": parse_json(row.input_json, {}),
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
