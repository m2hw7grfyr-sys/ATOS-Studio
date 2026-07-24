from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.ai import StudioEditorialBrief
from models.production import (
    StudioGenerationPipeline,
    StudioGenerationTask,
    StudioPersona,
    StudioSocialAccount,
    StudioVideoProject,
    StudioVideoScene,
)
from repositories.content_items import parse_json, stable_json
from services.gpt_prompt_builder import serialize_editorial_brief


PERSONA_STATUSES = {True, False}
SOCIAL_ACCOUNT_STATUSES = {"active", "inactive", "testing"}
VIDEO_PROJECT_STATUSES = {"draft", "planning", "ready_for_generation", "generating", "reviewing", "completed", "archived"}
VIDEO_SCENE_STATUSES = {"draft", "ready", "generating", "completed", "failed"}
CREATION_MODES = {"general", "persona"}
GENERATION_TASK_STATUSES = {"pending", "queued", "running", "paused", "completed", "failed", "cancelled"}
PIPELINE_STATUSES = {"draft", "planning", "queued", "running", "completed", "failed"}
GENERATION_TASK_TYPES = {
    "image_generation",
    "video_generation",
    "voice_generation",
    "subtitle_generation",
    "composition",
}


def clean_json(value: Any, fallback: Any) -> str:
    if isinstance(value, str):
        parsed = parse_json(value, fallback)
    else:
        parsed = value if value is not None else fallback
    return stable_json(parsed)


def serialize_persona(row: StudioPersona) -> dict[str, Any]:
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
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_social_account(row: StudioSocialAccount, persona: Optional[StudioPersona] = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "platform": row.platform,
        "username": row.username,
        "display_name": row.display_name,
        "persona_id": row.persona_id,
        "persona_name": persona.name if persona else None,
        "account_notes": row.account_notes,
        "status": row.status,
        "publishing_rules": parse_json(row.publishing_rules_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_video_scene(row: StudioVideoScene) -> dict[str, Any]:
    return {
        "id": row.id,
        "video_project_id": row.video_project_id,
        "scene_number": row.scene_number,
        "title": row.title,
        "purpose": row.purpose,
        "duration": row.duration,
        "visual_description": row.visual_description,
        "visual_prompt": row.visual_prompt,
        "image_prompt": row.image_prompt,
        "video_prompt": row.video_prompt,
        "negative_prompt": row.negative_prompt,
        "voiceover": row.voiceover,
        "subtitle": row.subtitle,
        "on_screen_text": row.on_screen_text,
        "camera_direction": row.camera_direction,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_generation_task(row: StudioGenerationTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "video_project_id": row.video_project_id,
        "scene_id": row.scene_id,
        "task_type": row.task_type,
        "provider": row.provider_name or row.provider,
        "provider_name": row.provider_name or row.provider,
        "provider_task_id": row.provider_task_id,
        "status": row.status,
        "current_step": row.current_step,
        "failed_step": row.failed_step,
        "priority": row.priority,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "retry_count": row.retry_count,
        "max_retry": row.max_retry,
        "depends_on_task_id": row.depends_on_task_id,
        "context": parse_json(row.context_json, {}),
        "input": parse_json(row.input_json, {}),
        "output": parse_json(row.output_json, {}),
        "preset_id": row.preset_id,
        "engine_id": row.engine_id,
        "model_profile_id": row.model_profile_id,
        "workflow_profile_id": row.workflow_profile_id,
        "configuration_version": row.configuration_version,
        "configuration_snapshot": parse_json(row.configuration_snapshot_json, {}),
        "preflight_result": parse_json(row.preflight_result_json, {}),
        "fallback_used": row.fallback_used,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_generation_pipeline(row: StudioGenerationPipeline) -> dict[str, Any]:
    return {
        "id": row.id,
        "video_project_id": row.video_project_id,
        "status": row.status,
        "current_stage": row.current_stage,
        "total_tasks": row.total_tasks,
        "completed_tasks": row.completed_tasks,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_video_project(db: Session, row: StudioVideoProject, include_detail: bool = False) -> dict[str, Any]:
    persona = db.get(StudioPersona, row.persona_id) if row.persona_id else None
    account = db.get(StudioSocialAccount, row.social_account_id) if row.social_account_id else None
    payload = {
        "id": row.id,
        "topic_package_id": row.topic_package_id,
        "editorial_brief_id": row.editorial_brief_id,
        "persona_id": row.persona_id,
        "persona_name": persona.name if persona else None,
        "social_account_id": row.social_account_id,
        "social_account": f"{account.platform} @{account.username}" if account else None,
        "creation_mode": row.creation_mode,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "review_status": row.review_status,
        "review_note": row.review_note,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "editorial_json_snapshot": row.editorial_json_snapshot,
        "editorial_parse_error": row.editorial_parse_error,
        "target_platforms": parse_json(row.target_platforms_json, []),
        "aspect_ratio": row.aspect_ratio,
        "duration_target": row.duration_target,
        "priority": row.priority,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_detail:
        scenes = db.scalars(
            select(StudioVideoScene)
            .where(StudioVideoScene.video_project_id == row.id)
            .order_by(StudioVideoScene.scene_number.asc())
        ).all()
        tasks = db.scalars(
            select(StudioGenerationTask)
            .where(StudioGenerationTask.video_project_id == row.id)
            .order_by(StudioGenerationTask.created_at.desc())
        ).all()
        pipelines = db.scalars(
            select(StudioGenerationPipeline)
            .where(StudioGenerationPipeline.video_project_id == row.id)
            .order_by(StudioGenerationPipeline.created_at.desc())
        ).all()
        brief = db.get(StudioEditorialBrief, row.editorial_brief_id)
        payload["scenes"] = [serialize_video_scene(scene) for scene in scenes]
        payload["generation_tasks"] = [serialize_generation_task(task) for task in tasks]
        payload["generation_pipelines"] = [serialize_generation_pipeline(pipeline) for pipeline in pipelines]
        payload["editorial_brief"] = serialize_editorial_brief(brief) if brief else None
        payload["persona"] = serialize_persona(persona) if persona else None
        payload["social_account_detail"] = serialize_social_account(account, persona) if account else None
    return payload


def list_personas(db: Session, enabled: Optional[bool] = None) -> list[dict[str, Any]]:
    statement = select(StudioPersona)
    if enabled is not None:
        statement = statement.where(StudioPersona.enabled.is_(enabled))
    rows = db.scalars(statement.order_by(StudioPersona.updated_at.desc())).all()
    return [serialize_persona(row) for row in rows]


def create_persona(db: Session, payload: dict[str, Any]) -> StudioPersona:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="persona name is required")
    row = StudioPersona(
        name=name,
        description=str(payload.get("description") or ""),
        target_audience=str(payload.get("target_audience") or ""),
        persona_profile_json=clean_json(payload.get("persona_profile") or payload.get("persona_profile_json"), {}),
        tone_style=str(payload.get("tone_style") or ""),
        language_style=str(payload.get("language_style") or ""),
        visual_style=str(payload.get("visual_style") or ""),
        voice_style=str(payload.get("voice_style") or ""),
        content_rules_json=clean_json(payload.get("content_rules") or payload.get("content_rules_json"), {}),
        enabled=bool(payload.get("enabled", True)),
    )
    db.add(row)
    db.flush()
    return row


def update_persona(db: Session, persona_id: str, payload: dict[str, Any]) -> StudioPersona:
    row = db.get(StudioPersona, persona_id)
    if not row:
        raise HTTPException(status_code=404, detail="persona not found")
    for field in ["name", "description", "target_audience", "tone_style", "language_style", "visual_style", "voice_style"]:
        if field in payload:
            setattr(row, field, str(payload.get(field) or ""))
    if "persona_profile" in payload or "persona_profile_json" in payload:
        row.persona_profile_json = clean_json(payload.get("persona_profile") or payload.get("persona_profile_json"), {})
    if "content_rules" in payload or "content_rules_json" in payload:
        row.content_rules_json = clean_json(payload.get("content_rules") or payload.get("content_rules_json"), {})
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    db.flush()
    return row


def list_social_accounts(db: Session, persona_id: Optional[str] = None, active_only: bool = False) -> list[dict[str, Any]]:
    statement = select(StudioSocialAccount)
    if persona_id:
        statement = statement.where(StudioSocialAccount.persona_id == persona_id)
    if active_only:
        statement = statement.where(StudioSocialAccount.status == "active")
    rows = db.scalars(statement.order_by(StudioSocialAccount.updated_at.desc())).all()
    return [serialize_social_account(row, db.get(StudioPersona, row.persona_id) if row.persona_id else None) for row in rows]


def create_social_account(db: Session, payload: dict[str, Any]) -> StudioSocialAccount:
    platform = str(payload.get("platform") or "").strip().lower()
    username = str(payload.get("username") or "").strip()
    if not platform or not username:
        raise HTTPException(status_code=422, detail="platform and username are required")
    status = str(payload.get("status") or "testing")
    if status not in SOCIAL_ACCOUNT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid social account status")
    persona_id = str(payload.get("persona_id") or "") or None
    if persona_id and not db.get(StudioPersona, persona_id):
        raise HTTPException(status_code=404, detail="persona not found")
    row = StudioSocialAccount(
        platform=platform,
        username=username,
        display_name=str(payload.get("display_name") or ""),
        persona_id=persona_id,
        account_notes=str(payload.get("account_notes") or ""),
        status=status,
        publishing_rules_json=clean_json(payload.get("publishing_rules") or payload.get("publishing_rules_json"), {}),
    )
    db.add(row)
    db.flush()
    return row


def update_social_account(db: Session, account_id: str, payload: dict[str, Any]) -> StudioSocialAccount:
    row = db.get(StudioSocialAccount, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="social account not found")
    if "persona_id" in payload:
        persona_id = str(payload.get("persona_id") or "") or None
        if persona_id and not db.get(StudioPersona, persona_id):
            raise HTTPException(status_code=404, detail="persona not found")
        row.persona_id = persona_id
    for field in ["platform", "username", "display_name", "account_notes", "status"]:
        if field in payload:
            value = str(payload.get(field) or "")
            if field == "platform":
                value = value.lower()
            if field == "status" and value not in SOCIAL_ACCOUNT_STATUSES:
                raise HTTPException(status_code=422, detail="invalid social account status")
            setattr(row, field, value)
    if "publishing_rules" in payload or "publishing_rules_json" in payload:
        row.publishing_rules_json = clean_json(payload.get("publishing_rules") or payload.get("publishing_rules_json"), {})
    db.flush()
    return row


def list_video_projects(db: Session, status: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(StudioVideoProject)
    if status:
        statement = statement.where(StudioVideoProject.status == status)
    rows = db.scalars(statement.order_by(StudioVideoProject.updated_at.desc())).all()
    return [serialize_video_project(db, row) for row in rows]


def create_video_project_from_brief(
    db: Session,
    editorial_brief_id: str,
    persona_id: Optional[str] = None,
    social_account_id: Optional[str] = None,
    priority: str = "normal",
    creation_mode: str = "persona",
) -> StudioVideoProject:
    brief = db.get(StudioEditorialBrief, editorial_brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="editorial brief not found")
    creation_mode = (creation_mode or "persona").strip().lower()
    if creation_mode not in CREATION_MODES:
        raise HTTPException(status_code=422, detail="invalid creation mode")
    persona_id = str(persona_id or "") or None
    social_account_id = str(social_account_id or "") or None
    persona = None
    if creation_mode == "persona":
        if not persona_id:
            raise HTTPException(status_code=422, detail="enabled persona is required")
        persona = db.get(StudioPersona, persona_id)
        if not persona or not persona.enabled:
            raise HTTPException(status_code=422, detail="enabled persona is required")
    elif persona_id:
        persona = db.get(StudioPersona, persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="persona not found")
    account = db.get(StudioSocialAccount, social_account_id) if social_account_id else None
    if social_account_id and not account:
        raise HTTPException(status_code=404, detail="social account not found")
    if creation_mode == "general" and account:
        raise HTTPException(status_code=422, detail="general mode does not bind social account")
    if account and account.persona_id != persona_id:
        raise HTTPException(status_code=422, detail="social account must belong to selected persona")
    output = parse_json(brief.output_json, {}) or parse_json(brief.input_json, {})
    target_platforms = [account.platform] if account else []
    scenes = output.get("scenes") or []
    duration_target = int(sum(float(scene.get("duration") or 0) for scene in scenes if isinstance(scene, dict)) or 0)
    project = StudioVideoProject(
        topic_package_id=brief.topic_package_id,
        editorial_brief_id=brief.id,
        persona_id=persona.id if persona else None,
        social_account_id=account.id if account else None,
        creation_mode=creation_mode,
        title=str(output.get("title") or "Untitled Video Project"),
        description=str(output.get("hook") or output.get("script") or ""),
        status="draft",
        review_status="draft",
        editorial_json_snapshot=stable_json(output),
        target_platforms_json=stable_json(target_platforms),
        aspect_ratio="9:16",
        duration_target=duration_target or None,
        priority=priority or "normal",
    )
    db.add(project)
    db.flush()
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        db.add(
            StudioVideoScene(
                video_project_id=project.id,
                scene_number=int(scene.get("scene_number") or index),
                title=str(scene.get("title") or f"Scene {index}"),
                purpose=str(scene.get("purpose") or ""),
                duration=float(scene.get("duration") or 0),
                visual_description=str(scene.get("visual_description") or scene.get("visual_prompt") or ""),
                visual_prompt=str(scene.get("visual_prompt") or ""),
                image_prompt=str(scene.get("image_prompt") or scene.get("visual_prompt") or ""),
                video_prompt=str(scene.get("video_prompt") or ""),
                negative_prompt=str(scene.get("negative_prompt") or ""),
                voiceover=str(scene.get("voiceover") or ""),
                subtitle=str(scene.get("subtitle") or ""),
                on_screen_text=str(scene.get("on_screen_text") or scene.get("subtitle") or ""),
                camera_direction=str(scene.get("camera_direction") or ""),
                status="draft",
            )
        )
    db.flush()
    return project
