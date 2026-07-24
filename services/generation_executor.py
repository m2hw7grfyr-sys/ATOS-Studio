from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.production import (
    StudioAsset,
    StudioGenerationTask,
    StudioGenerationWorkflow,
    StudioModelCapability,
    StudioVideoProject,
    StudioVideoScene,
)
from repositories.content_items import parse_json, stable_json
from services.generation.provider_registry import get_generation_provider
from services.generation_steps import GenerationStep, IMAGE_GENERATION_FLOW
from services.generation_planner import generation_context
from services.video_production import serialize_generation_task
from services.workflow_validator import validate_workflow


logger = logging.getLogger(__name__)


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
        "description": row.description,
        "provider": row.provider,
        "workflow_type": row.workflow_type,
        "status": row.status,
        "workflow": parse_json(row.workflow_json, {}),
        "tags": parse_json(row.tags_json, []),
        "required_models": parse_json(row.required_models_json, []),
        "test_result": parse_json(row.test_result_json, {}),
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
        "created_by": row.created_by,
        "version": row.version,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_model_capability(row: StudioModelCapability) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "model_type": row.model_type,
        "version": row.version,
        "status": row.status,
        "metadata": parse_json(row.metadata_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def enabled_workflow(db: Session, provider: str, workflow_type: str) -> StudioGenerationWorkflow:
    row = db.scalars(
        select(StudioGenerationWorkflow)
        .where(StudioGenerationWorkflow.provider == provider)
        .where(StudioGenerationWorkflow.workflow_type == workflow_type)
        .where(StudioGenerationWorkflow.enabled.is_(True))
        .where(StudioGenerationWorkflow.status == "available")
        .order_by(StudioGenerationWorkflow.updated_at.desc())
    ).first()
    if not row:
        raise HTTPException(status_code=422, detail=f"available workflow not found for {provider}/{workflow_type}")
    return row


def create_workflow(db: Session, payload: dict[str, Any]) -> StudioGenerationWorkflow:
    name = str(payload.get("name") or "").strip()
    provider = str(payload.get("provider") or "").strip().lower()
    workflow_type = str(payload.get("workflow_type") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="workflow name is required")
    workflow_payload = payload.get("workflow") or payload.get("workflow_json") or "{}"
    try:
        validate_workflow(provider, workflow_type, workflow_payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = StudioGenerationWorkflow(
        name=name,
        description=str(payload.get("description") or ""),
        provider=provider,
        workflow_type=workflow_type,
        status=str(payload.get("status") or "draft"),
        workflow_json=stable_json(parse_json(workflow_payload, workflow_payload if isinstance(workflow_payload, dict) else {})),
        tags_json=stable_json(payload.get("tags") or []),
        required_models_json=stable_json(payload.get("required_models") or []),
        test_result_json="{}",
        version=str(payload.get("version") or "v1"),
        enabled=bool(payload.get("enabled", True)),
        created_by=str(payload.get("created_by") or "operator"),
    )
    db.add(row)
    db.flush()
    return row


def update_workflow(db: Session, workflow_id: str, payload: dict[str, Any]) -> StudioGenerationWorkflow:
    row = db.get(StudioGenerationWorkflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    for field in ["name", "description", "provider", "workflow_type", "status", "version", "created_by"]:
        if field in payload:
            value = str(payload.get(field) or "")
            if field == "provider":
                value = value.lower()
            setattr(row, field, value)
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    if "workflow" in payload or "workflow_json" in payload:
        workflow_payload = payload.get("workflow") or payload.get("workflow_json")
        try:
            validate_workflow(row.provider, row.workflow_type, workflow_payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.workflow_json = stable_json(parse_json(workflow_payload, workflow_payload if isinstance(workflow_payload, dict) else {}))
    if "tags" in payload:
        row.tags_json = stable_json(payload.get("tags") or [])
    if "required_models" in payload:
        row.required_models_json = stable_json(payload.get("required_models") or [])
    db.flush()
    return row


def create_model_capability(db: Session, payload: dict[str, Any]) -> StudioModelCapability:
    name = str(payload.get("name") or "").strip()
    provider = str(payload.get("provider") or "").strip().lower()
    model_type = str(payload.get("model_type") or "").strip()
    status = str(payload.get("status") or "missing").strip()
    if not name or not provider or not model_type:
        raise HTTPException(status_code=422, detail="name, provider and model_type are required")
    if status not in {"available", "missing", "disabled"}:
        raise HTTPException(status_code=422, detail="invalid model capability status")
    row = StudioModelCapability(
        name=name,
        provider=provider,
        model_type=model_type,
        version=str(payload.get("version") or ""),
        status=status,
        metadata_json=stable_json(payload.get("metadata") or {}),
    )
    db.add(row)
    db.flush()
    return row


def update_model_capability(db: Session, model_id: str, payload: dict[str, Any]) -> StudioModelCapability:
    row = db.get(StudioModelCapability, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="model capability not found")
    for field in ["name", "provider", "model_type", "version", "status"]:
        if field in payload:
            value = str(payload.get(field) or "")
            if field == "provider":
                value = value.lower()
            if field == "status" and value not in {"available", "missing", "disabled"}:
                raise HTTPException(status_code=422, detail="invalid model capability status")
            setattr(row, field, value)
    if "metadata" in payload:
        row.metadata_json = stable_json(payload.get("metadata") or {})
    db.flush()
    return row


def list_model_capabilities(db: Session, provider: Optional[str] = None, model_type: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(StudioModelCapability)
    if provider:
        statement = statement.where(StudioModelCapability.provider == provider)
    if model_type:
        statement = statement.where(StudioModelCapability.model_type == model_type)
    if status:
        statement = statement.where(StudioModelCapability.status == status)
    rows = db.scalars(statement.order_by(StudioModelCapability.updated_at.desc())).all()
    return [serialize_model_capability(row) for row in rows]


def required_models_available(db: Session, workflow: StudioGenerationWorkflow) -> tuple[bool, list[str]]:
    missing = []
    for item in parse_json(workflow.required_models_json, []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        model_type = str(item.get("type") or item.get("model_type") or "").strip()
        if not name:
            continue
        statement = select(StudioModelCapability).where(StudioModelCapability.provider == workflow.provider).where(StudioModelCapability.name == name)
        if model_type:
            statement = statement.where(StudioModelCapability.model_type == model_type)
        row = db.scalars(statement.where(StudioModelCapability.status == "available")).first()
        if not row:
            missing.append(name)
    return not missing, missing


def preflight_generation_task(db: Session, task: StudioGenerationTask, workflow: StudioGenerationWorkflow) -> dict[str, Any]:
    provider_name = task.provider_name or task.provider or workflow.provider
    if not workflow.enabled or workflow.status != "available":
        return {"ok": False, "reason": "workflow_not_available"}
    provider = get_generation_provider(provider_name)
    health = provider.health_check()
    if not health.get("available"):
        return {"ok": False, "reason": "provider_offline", "provider_health": health}
    model_ok, missing_models = required_models_available(db, workflow)
    if not model_ok:
        return {"ok": False, "reason": "missing_model", "missing_models": missing_models}
    return {"ok": True, "reason": "ok", "provider_health": health}


def task_output(task: StudioGenerationTask) -> dict[str, Any]:
    return parse_json(task.output_json, {}) or {}


def save_task_output(task: StudioGenerationTask, payload: dict[str, Any]) -> None:
    task.output_json = stable_json(payload)


def completed_steps(task: StudioGenerationTask) -> list[str]:
    steps = task_output(task).get("completed_steps") or []
    return [str(step) for step in steps]


def mark_step_started(task: StudioGenerationTask, step: str) -> None:
    task.status = "running"
    task.current_step = step
    task.failed_step = ""
    task.error_message = None
    task.started_at = task.started_at or utc_now()
    task.updated_at = utc_now()


def mark_step_completed(task: StudioGenerationTask, step: str, payload: Optional[dict[str, Any]] = None) -> None:
    output = task_output(task)
    steps = [str(item) for item in output.get("completed_steps") or []]
    if step not in steps:
        steps.append(step)
    output["completed_steps"] = steps
    if payload:
        output[step] = payload
    save_task_output(task, output)
    task.current_step = step
    task.updated_at = utc_now()


def mark_task_failed(task: StudioGenerationTask, step: str, error_message: str, payload: Optional[dict[str, Any]] = None) -> None:
    output = task_output(task)
    output["failed_step"] = step
    if payload:
        output[step] = payload
    save_task_output(task, output)
    task.status = "failed"
    task.current_step = step
    task.failed_step = step
    task.finished_at = utc_now()
    task.error_message = error_message[:1000]
    task.updated_at = utc_now()


def mark_task_completed(task: StudioGenerationTask) -> None:
    now = utc_now()
    task.status = "completed"
    task.current_step = GenerationStep.ARCHIVE
    task.failed_step = ""
    task.finished_at = now
    task.completed_at = now
    task.updated_at = now


def fail_task_from_exception(task: StudioGenerationTask, step: str, exc: Exception, payload: Optional[dict[str, Any]] = None) -> None:
    logger.exception("generation task failed", extra={"task_id": task.id, "step": step})
    mark_task_failed(task, step, str(exc) or exc.__class__.__name__, payload)


def fail_task_from_reason(task: StudioGenerationTask, step: str, reason: str, payload: Optional[dict[str, Any]] = None) -> None:
    logger.error("generation task failed: %s", reason, extra={"task_id": task.id, "step": step})
    mark_task_failed(task, step, reason, payload)


def first_step_to_run(task: StudioGenerationTask, retry_from_failed: bool = False) -> str:
    if retry_from_failed and task.failed_step:
        return task.failed_step
    done = set(completed_steps(task))
    for step in IMAGE_GENERATION_FLOW:
        if step not in done:
            return step
    return GenerationStep.ARCHIVE


def step_should_run(task: StudioGenerationTask, step: str, start_step: str) -> bool:
    if step == start_step:
        return True
    if step in completed_steps(task):
        return False
    try:
        return IMAGE_GENERATION_FLOW.index(step) > IMAGE_GENERATION_FLOW.index(start_step)
    except ValueError:
        return True


def existing_task_assets(db: Session, task: StudioGenerationTask) -> list[StudioAsset]:
    return db.scalars(
        select(StudioAsset)
        .where(StudioAsset.generation_task_id == task.id)
        .order_by(StudioAsset.created_at.desc())
    ).all()


def asset_already_saved(db: Session, task: StudioGenerationTask, asset_payload: dict[str, Any]) -> bool:
    url = str(asset_payload.get("url") or "")
    file_path = str(asset_payload.get("file_path") or "")
    if not url and not file_path:
        return False
    statement = select(StudioAsset).where(StudioAsset.generation_task_id == task.id)
    if url:
        statement = statement.where(StudioAsset.url == url)
    if file_path:
        statement = statement.where(StudioAsset.file_path == file_path)
    return db.scalars(statement).first() is not None


def create_scene_image_task(db: Session, scene_id: str, provider_name: str = "comfyui", workflow_id: Optional[str] = None) -> StudioGenerationTask:
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    project = db.get(StudioVideoProject, scene.video_project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    context = generation_context(project, scene)
    context["visual_prompt"] = scene.image_prompt or scene.visual_prompt or scene.visual_description
    if workflow_id:
        context["workflow_id"] = workflow_id
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


def run_generation_task(db: Session, task_id: str, retry_from_failed: bool = False) -> dict[str, Any]:
    task = db.get(StudioGenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="generation task not found")
    if task.task_type != "image_generation":
        raise HTTPException(status_code=422, detail="only image_generation is executable in Sprint 10")
    if task.status == "running":
        raise HTTPException(status_code=409, detail="generation task is already running")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="completed generation task cannot be rerun")
    if retry_from_failed and task.status != "failed":
        raise HTTPException(status_code=409, detail="only failed generation tasks can be retried")
    if retry_from_failed:
        task.retry_count += 1
    provider_name = task.provider_name or task.provider or "comfyui"
    context = parse_json(task.context_json, {})
    workflow: Optional[StudioGenerationWorkflow] = None
    provider = None
    start_step = first_step_to_run(task, retry_from_failed)
    try:
        if step_should_run(task, GenerationStep.PREPARE, start_step):
            mark_step_started(task, GenerationStep.PREPARE)
            db.flush()
            workflow_id = context.get("workflow_id")
            if workflow_id:
                workflow = db.get(StudioGenerationWorkflow, str(workflow_id))
                if not workflow:
                    raise HTTPException(status_code=404, detail="workflow not found")
            else:
                workflow = enabled_workflow(db, provider_name, task.task_type)
            preflight = preflight_generation_task(db, task, workflow)
            if not preflight.get("ok"):
                fail_task_from_reason(
                    task,
                    GenerationStep.PREPARE,
                    str(preflight.get("reason") or "preflight_failed"),
                    {"preflight": preflight},
                )
                db.flush()
                return {"task": serialize_generation_task(task), "assets": []}
            mark_step_completed(task, GenerationStep.PREPARE, {"preflight": preflight, "workflow_id": workflow.id})
            db.flush()
        else:
            workflow_id = context.get("workflow_id") or task_output(task).get(GenerationStep.PREPARE, {}).get("workflow_id")
            workflow = db.get(StudioGenerationWorkflow, str(workflow_id)) if workflow_id else enabled_workflow(db, provider_name, task.task_type)
        if step_should_run(task, GenerationStep.IMAGE_GENERATION, start_step):
            mark_step_started(task, GenerationStep.IMAGE_GENERATION)
            db.flush()
            existing_assets = existing_task_assets(db, task)
            if existing_assets and retry_from_failed:
                mark_step_completed(
                    task,
                    GenerationStep.IMAGE_GENERATION,
                    {"skipped": True, "reason": "existing_asset", "asset_count": len(existing_assets)},
                )
            else:
                provider = get_generation_provider(provider_name)
                submitted = provider.submit_job(parse_json(workflow.workflow_json, {}), context)
                task.provider_task_id = str(submitted.get("provider_task_id") or "")
                status_payload = provider.get_status(task.provider_task_id)
                result_payload = provider.get_result(task.provider_task_id)
                assets_payload = result_payload.get("assets") or []
                saved_count = 0
                for asset_payload in assets_payload:
                    if asset_already_saved(db, task, asset_payload):
                        continue
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
                    saved_count += 1
                if not assets_payload and not existing_task_assets(db, task):
                    raise RuntimeError("Workflow execution failed.")
                mark_step_completed(
                    task,
                    GenerationStep.IMAGE_GENERATION,
                    {
                        "submit": submitted,
                        "status": status_payload,
                        "result": result_payload,
                        "asset_count": len(assets_payload),
                        "saved_asset_count": saved_count,
                    },
                )
            db.flush()
        if step_should_run(task, GenerationStep.ARCHIVE, start_step):
            mark_step_started(task, GenerationStep.ARCHIVE)
            db.flush()
            if not existing_task_assets(db, task):
                raise RuntimeError("Workflow execution failed.")
            mark_step_completed(task, GenerationStep.ARCHIVE, {"asset_count": len(existing_task_assets(db, task))})
            mark_task_completed(task)
        db.flush()
    except Exception as exc:
        if isinstance(exc, HTTPException):
            if exc.status_code in {404, 409, 422} and not task.current_step:
                raise
            message = str(exc.detail)
        else:
            message = str(exc)
        fail_task_from_exception(task, task.current_step or start_step, exc, {"error": message})
        db.flush()
    assets = existing_task_assets(db, task)
    return {"task": serialize_generation_task(task), "assets": [serialize_asset(asset) for asset in assets]}


def retry_generation_task(db: Session, task_id: str) -> dict[str, Any]:
    task = db.get(StudioGenerationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="generation task not found")
    if task.status != "failed":
        raise HTTPException(status_code=409, detail="only failed generation tasks can be retried")
    if not task.failed_step:
        raise HTTPException(status_code=409, detail="failed_step is missing")
    return run_generation_task(db, task_id, retry_from_failed=True)


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


def list_workflows(db: Session, provider: Optional[str] = None, workflow_type: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(StudioGenerationWorkflow)
    if provider:
        statement = statement.where(StudioGenerationWorkflow.provider == provider)
    if workflow_type:
        statement = statement.where(StudioGenerationWorkflow.workflow_type == workflow_type)
    if status:
        statement = statement.where(StudioGenerationWorkflow.status == status)
    rows = db.scalars(statement.order_by(StudioGenerationWorkflow.updated_at.desc())).all()
    return [serialize_workflow(row) for row in rows]


def test_workflow(db: Session, workflow_id: str, visual_prompt: str = "A simple test image") -> dict[str, Any]:
    workflow = db.get(StudioGenerationWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    workflow.status = "testing"
    workflow.last_tested_at = utc_now()
    db.flush()
    try:
        validate_workflow(workflow.provider, workflow.workflow_type, parse_json(workflow.workflow_json, {}))
        provider = get_generation_provider(workflow.provider)
        health = provider.health_check()
        if not health.get("available"):
            raise RuntimeError("provider_offline")
        model_ok, missing_models = required_models_available(db, workflow)
        if not model_ok:
            raise RuntimeError(f"missing_model: {', '.join(missing_models)}")
        started = utc_now()
        submitted = provider.submit_job(parse_json(workflow.workflow_json, {}), {"visual_prompt": visual_prompt})
        result = provider.get_result(str(submitted.get("provider_task_id") or ""))
        duration = (utc_now() - started).total_seconds()
        image = ""
        assets = result.get("assets") or []
        if assets:
            image = str(assets[0].get("url") or assets[0].get("file_path") or "")
        payload = {"success": True, "image": image, "duration": duration, "error": "", "result": result}
        workflow.status = "available"
        workflow.test_result_json = stable_json(payload)
        workflow.last_tested_at = utc_now()
        db.flush()
        return serialize_workflow(workflow)
    except Exception as exc:
        payload = {"success": False, "image": "", "duration": "", "error": str(exc)}
        workflow.status = "draft"
        workflow.test_result_json = stable_json(payload)
        workflow.last_tested_at = utc_now()
        db.flush()
        return serialize_workflow(workflow)
