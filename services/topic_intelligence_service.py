from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.ai import StudioAIAnalysis, StudioAIJob
from models.content_item import StudioContentItem, utc_now
from models.topic_package import StudioTopicPackage, StudioTopicPackageItem
from repositories.content_items import parse_json, stable_json
from schemas.topic_intelligence import parse_topic_intelligence_json
from services.ai.providers.llm_provider import LLMGeneration


TOPIC_INTELLIGENCE_JOB_TYPE = "topic_intelligence_analysis"
TOPIC_INTELLIGENCE_ANALYSIS_TYPE = "topic_intelligence"
TOPIC_INTELLIGENCE_PROMPT_CATEGORY = "topic_intelligence"


METRIC_KEYS = {
    "score": ["score", "source_score"],
    "upvotes": ["upvotes", "upvote_count", "ups"],
    "likes": ["likes", "like_count"],
    "comments_count": ["comments_count", "comment_count", "num_comments"],
    "views": ["views", "view_count"],
    "reposts": ["reposts", "repost_count", "shares"],
    "bookmarks": ["bookmarks", "bookmark_count", "saves"],
}


COMMENT_KEYS = ["comments", "raw_comments", "comments_json", "top_comments", "comment_items"]


def first_value(*sources: dict[str, Any], keys: list[str], fallback: Any = None) -> Any:
    for source in sources:
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return fallback


def normalize_comment(raw: Any, index: int, source_url: Optional[str]) -> dict[str, Any]:
    if isinstance(raw, str):
        return {"text": raw, "likes": None, "reply_count": None, "author": None, "source": source_url}
    if not isinstance(raw, dict):
        return {"text": str(raw), "likes": None, "reply_count": None, "author": None, "source": source_url}
    text = raw.get("text") or raw.get("body") or raw.get("comment") or raw.get("content") or ""
    return {
        "text": text,
        "likes": raw.get("likes") or raw.get("score") or raw.get("upvotes"),
        "reply_count": raw.get("reply_count") or raw.get("replies") or raw.get("comments_count"),
        "author": raw.get("author") or raw.get("username"),
        "source": raw.get("source_url") or source_url,
        "position": index,
    }


def extract_comments(metadata: dict[str, Any], snapshot: dict[str, Any], source_url: Optional[str]) -> list[dict[str, Any]]:
    raw_comments: Any = None
    for source in [metadata, snapshot]:
        for key in COMMENT_KEYS:
            if key in source and source[key]:
                raw_comments = source[key]
                break
        if raw_comments:
            break
    if isinstance(raw_comments, str):
        try:
            raw_comments = json.loads(raw_comments)
        except Exception:
            raw_comments = [raw_comments]
    if not isinstance(raw_comments, list):
        return []
    return [normalize_comment(item, index + 1, source_url) for index, item in enumerate(raw_comments)]


def content_context(row: StudioContentItem) -> dict[str, Any]:
    metadata = parse_json(row.metadata_json, {})
    snapshot = parse_json(row.source_snapshot_json, {})
    metrics = {}
    for target_key, keys in METRIC_KEYS.items():
        fallback = row.source_score if target_key == "score" else row.comment_count if target_key == "comments_count" else None
        metrics[target_key] = first_value(metadata, snapshot, keys=keys, fallback=fallback)
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "source_platform": row.source_platform,
        "source_url": row.source_url,
        "author": row.author,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "metrics": metrics,
        "comments": extract_comments(metadata, snapshot, row.source_url),
    }


def build_topic_intelligence_context(db: Session, topic_package_id: str) -> dict[str, Any]:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    links = db.scalars(
        select(StudioTopicPackageItem)
        .where(
            StudioTopicPackageItem.topic_package_id == topic_package_id,
            StudioTopicPackageItem.removed_at.is_(None),
        )
        .order_by(StudioTopicPackageItem.position.asc(), StudioTopicPackageItem.added_at.asc())
    ).all()
    contents = []
    for link in links:
        row = db.get(StudioContentItem, link.content_item_id)
        if row:
            item = content_context(row)
            item["is_primary"] = link.is_primary
            item["position"] = link.position
            contents.append(item)
    return {
        "topic_package": {
            "id": package.id,
            "title": package.title,
            "summary": package.summary,
            "content_angle": package.content_angle,
            "status": package.status,
            "risk_level": package.risk_level,
            "priority": package.priority,
            "source_count": package.source_count,
            "total_comment_count": package.total_comment_count,
            "average_source_score": package.average_source_score,
            "max_source_score": package.max_source_score,
            "target_content_type": package.target_content_type,
            "target_platforms": parse_json(package.target_platforms_json, []),
        },
        "contents": contents,
    }


def render_topic_intelligence_prompt(template: str, context: dict[str, Any]) -> str:
    required_schema = {
        "core_summary": "",
        "audience": {"persona": "", "needs": []},
        "pain_points": [{"problem": "", "frequency": "", "emotion": ""}],
        "emotional_triggers": [],
        "controversies": [],
        "user_quotes": [{"quote": "", "source": "", "engagement": 0}],
        "content_opportunities": [{"angle": "", "reason": "", "recommended_format": ""}],
        "video_direction": {"recommended_hook": "", "recommended_style": "", "target_platforms": []},
        "opportunity_score": {"total": 0, "engagement": 0, "comment_quality": 0, "emotion": 0, "commercial": 0},
    }
    return (
        f"{template}\n\n"
        "请只输出严格 JSON，不要输出 Markdown，不要添加解释。\n"
        f"必须符合以下结构：\n{json.dumps(required_schema, ensure_ascii=False, indent=2)}\n\n"
        f"主题包分析上下文 JSON：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def create_topic_intelligence_job(db: Session, topic_package_id: str) -> StudioAIJob:
    context = build_topic_intelligence_context(db, topic_package_id)
    job = StudioAIJob(
        job_type=TOPIC_INTELLIGENCE_JOB_TYPE,
        entity_type="topic_package",
        entity_id=topic_package_id,
        status="pending",
        input_snapshot=stable_json(context),
    )
    db.add(job)
    db.flush()
    return job


def run_topic_intelligence_job(db: Session, job_id: str, provider_override=None) -> StudioAIJob:
    from services.ai_service import active_prompt_for_category, get_ai_provider

    job = db.get(StudioAIJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ai job not found")
    if job.job_type != TOPIC_INTELLIGENCE_JOB_TYPE:
        raise HTTPException(status_code=422, detail="not a topic intelligence job")
    if job.status == "cancelled":
        raise HTTPException(status_code=422, detail="cancelled job cannot run")
    template = active_prompt_for_category(db, TOPIC_INTELLIGENCE_PROMPT_CATEGORY)
    context = parse_json(job.input_snapshot, {})
    prompt = render_topic_intelligence_prompt(template.template, context)
    provider = provider_override or get_ai_provider()
    job.status = "running"
    job.started_at = utc_now()
    job.provider = getattr(provider, "provider_name", "unknown")
    job.model = provider.get_model_info().get("model")
    db.flush()
    try:
        generation: LLMGeneration = provider.generate(prompt)
        result = parse_topic_intelligence_json(generation.text)
        job.status = "completed"
        job.output_json = stable_json(result)
        job.provider = generation.provider
        job.model = generation.model
        job.error_message = None
        db.add(
            StudioAIAnalysis(
                topic_package_id=job.entity_id,
                analysis_type=TOPIC_INTELLIGENCE_ANALYSIS_TYPE,
                result_json=stable_json(result),
                provider=generation.provider,
                model=generation.model,
                prompt_version=template.version,
            )
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:1000]
    finally:
        job.finished_at = utc_now()
        db.flush()
    return job
