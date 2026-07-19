from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.production import (
    StudioAsset,
    StudioGenerationTask,
    StudioGenerationWorkflow,
    StudioVideoProject,
    StudioVideoScene,
)
from repositories.content_items import parse_json, stable_json
from services.generation.provider_registry import get_generation_provider
from services.generation_planner import generation_context
from services.video_production import serialize_generation_task


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_asset(row: StudioAsset) -> dict[str, Any]:
    return {
        "id": row.id,
        "asset_type": row.asset_type,
        "file_path": row.file_path,
        "url": row.url,
        "provider": row.provider,
        "generation_task_id": row.generation_task_id,
        "metadata": parse_json(row.metadata_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_workflow(row: StudioGenerationWorkflow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "workflow_type": row.workflow_type,
        "workflow": parse_json(row.workflow_json, {}),
        "version": row.version,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def enabled_workflow(db: Session, provider: str, workflow_type: str) -> StudioGenerationWorkflow:
    row = db.scalars(
        select(StudioGenerationWorkflow)
        .where(StudioGenerationWorkflow.provider == provider)
        .where(StudioGenerationWorkflow.workflow_type == workflow_type)
        .where(StudioGenerationWorkflow.enabled.is_(True))
        .order_by(StudioGenerationWorkflow.updated_at.desc())
    ).first()
    if not row:
        raise HTTPException(status_code=422, detail=f"enabled workflow not found for {provider}/{workflow_type}")
    return row


def create_scene_image_task(db: Session, scene_id: str, provider_name: str = "comfyui") -> StudioGenerationTask:
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    project = db.get(StudioVideoProject, scene.video_project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    context = generation_context(project, scene)
    context["visual_prompt"] = scene.visual_prompt
    task = StudioGenerationTask(
        video_project_id=project.id,
        scene_id=scene.id,
        task_type="image_generation",
        provider=provider_name,
        provider_name=provider_name,
        status="queued",
        priority=project.priority or "normal",
        context_json=stable_json(context),
        input_json=stable_json({"context": context}),
        output_json="{}",
        max_retry=3,
    )
    db.add(task)
    db.flush()
    return task


def run_generation_task(db: Session, task_id: str) -> dict[str, Any]:
    task = db.get(StudioGenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="generation task not found")
    if task.task_type != "image_generation":
        raise HTTPException(status_code=422, detail="only image_generation is executable in Sprint 10")
    provider_name = task.provider_name or task.provider or "comfyui"
    workflow = enabled_workflow(db, provider_name, task.task_type)
    provider = get_generation_provider(provider_name)
    context = parse_json(task.context_json, {})
    task.status = "running"
    task.started_at = task.started_at or utc_now()
    task.error_message = None
    db.flush()
    try:
        submitted = provider.submit_job(parse_json(workflow.workflow_json, {}), context)
        task.provider_task_id = str(submitted.get("provider_task_id") or "")
        status_payload = provider.get_status(task.provider_task_id)
        result_payload = provider.get_result(task.provider_task_id)
        assets_payload = result_payload.get("assets") or []
        for asset_payload in assets_payload:
            db.add(
                StudioAsset(
                    asset_type=str(asset_payload.get("asset_type") or "image"),
                    file_path=str(asset_payload.get("file_path") or ""),
                    url=str(asset_payload.get("url") or ""),
                    provider=provider_name,
                    generation_task_id=task.id,
                    metadata_json=stable_json(asset_payload.get("metadata") or {}),
                )
            )
        if assets_payload:
            task.status = "completed"
            task.finished_at = utc_now()
        else:
            task.status = "running"
        task.output_json = stable_json(
            {
                "submit": submitted,
                "status": status_payload,
                "result": result_payload,
                "asset_count": len(assets_payload),
            }
        )
        db.flush()
    except Exception as exc:
        task.status = "failed"
        task.finished_at = utc_now()
        task.error_message = str(exc)[:1000]
        task.output_json = stable_json({"error": task.error_message})
        db.flush()
    assets = db.scalars(
        select(StudioAsset)
        .where(StudioAsset.generation_task_id == task.id)
        .order_by(StudioAsset.created_at.desc())
    ).all()
    return {"task": serialize_generation_task(task), "assets": [serialize_asset(asset) for asset in assets]}


def scene_assets(db: Session, scene_id: str) -> list[dict[str, Any]]:
    tasks = db.scalars(
        select(StudioGenerationTask.id)
        .where(StudioGenerationTask.scene_id == scene_id)
        .where(StudioGenerationTask.task_type == "image_generation")
    ).all()
    if not tasks:
        return []
    rows = db.scalars(
        select(StudioAsset)
        .where(StudioAsset.generation_task_id.in_(tasks))
        .order_by(StudioAsset.created_at.desc())
    ).all()
    return [serialize_asset(row) for row in rows]


def task_assets(db: Session, task_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(StudioAsset)
        .where(StudioAsset.generation_task_id == task_id)
        .order_by(StudioAsset.created_at.desc())
    ).all()
    return [serialize_asset(row) for row in rows]


def list_workflows(db: Session, provider: Optional[str] = None, workflow_type: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(StudioGenerationWorkflow)
    if provider:
        statement = statement.where(StudioGenerationWorkflow.provider == provider)
    if workflow_type:
        statement = statement.where(StudioGenerationWorkflow.workflow_type == workflow_type)
    rows = db.scalars(statement.order_by(StudioGenerationWorkflow.updated_at.desc())).all()
    return [serialize_workflow(row) for row in rows]
