from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import get_settings
from models.production import (
    StudioGenerationConfigSnapshot,
    StudioGenerationPreset,
    StudioGenerationTask,
    StudioGenerationWorkflow,
    StudioModelCapability,
    StudioPreflightResult,
    StudioVideoProject,
    StudioVideoScene,
)
from repositories.content_items import parse_json, stable_json
from services.generation.provider_registry import get_generation_engine, list_generation_engines
from services.workflow_validator import validate_workflow


CONFIGURATION_VERSION = "1"
TASK_TYPE_CAPABILITY = {
    "image_generation": "image",
    "video_generation": "video",
    "voice_generation": "tts",
    "subtitle_generation": "subtitle",
    "composition": "composition",
}
GENERATION_ERROR_CODES = {
    "ENGINE_NOT_CONFIGURED",
    "ENGINE_UNREACHABLE",
    "MODEL_NOT_FOUND",
    "WORKFLOW_NOT_FOUND",
    "WORKFLOW_INVALID",
    "CUSTOM_NODE_MISSING",
    "FFMPEG_NOT_FOUND",
    "OUTPUT_DIRECTORY_UNWRITABLE",
    "INSUFFICIENT_DISK_SPACE",
    "GPU_NOT_FOUND",
    "INSUFFICIENT_VRAM",
    "UNSUPPORTED_RESOLUTION",
    "UNSUPPORTED_DURATION",
    "UNSUPPORTED_FPS",
    "INVALID_GENERATION_CONFIG",
}
DEFAULT_MODEL_ID = "model-comfyui-default-image"
DEFAULT_PRESET_ID = "preset-image-scene-default"
FAST_PRESET_ID = "preset-image-scene-fast"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def capability_for_task_type(task_type: str) -> str:
    return TASK_TYPE_CAPABILITY.get(task_type, task_type.replace("_generation", ""))


def public_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = Path(text).parts
    if ".." in parts:
        raise HTTPException(status_code=422, detail="path traversal is not allowed")
    return text


def check_path_safe(value: str, label: str, checks: list[dict[str, Any]], blocking: bool = True) -> bool:
    try:
        public_path(value)
        return True
    except HTTPException:
        checks.append(
            {
                "code": "INVALID_GENERATION_CONFIG",
                "status": "failed",
                "message": f"{label} contains an unsafe path.",
                "details": {"field": label},
                "blocking": blocking,
            }
        )
        return False


def serialize_model_profile(row: StudioModelCapability) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "display_name": row.display_name or row.name,
        "provider": row.provider,
        "engine_id": row.engine_id or row.provider,
        "capability": row.capability or row.model_type,
        "model_type": row.model_type,
        "model_identifier": row.model_identifier,
        "workflow_path": row.workflow_path,
        "checkpoint_path": row.checkpoint_path,
        "vae_path": row.vae_path,
        "lora_paths": parse_json(row.lora_paths_json, []),
        "enabled": row.enabled,
        "is_default": row.is_default,
        "priority": row.priority,
        "estimated_vram_gb": row.estimated_vram_gb,
        "supported_widths": parse_json(row.supported_widths_json, []),
        "supported_heights": parse_json(row.supported_heights_json, []),
        "supported_durations": parse_json(row.supported_durations_json, []),
        "supported_fps": parse_json(row.supported_fps_json, []),
        "supported_aspect_ratios": parse_json(row.supported_aspect_ratios_json, []),
        "default_parameters": parse_json(row.default_parameters_json, {}),
        "validation_rules": parse_json(row.validation_rules_json, {}),
        "version": row.version,
        "status": row.status,
        "metadata": parse_json(row.metadata_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_generation_preset(row: StudioGenerationPreset) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "display_name": row.display_name or row.name,
        "capability": row.capability,
        "engine_id": row.engine_id,
        "model_profile_id": row.model_profile_id,
        "workflow_profile_id": row.workflow_profile_id,
        "parameters": parse_json(row.parameters_json, {}),
        "timeout_seconds": row.timeout_seconds,
        "max_attempts": row.max_attempts,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "priority": row.priority,
        "fallback_preset_id": row.fallback_preset_id,
        "remark": row.remark,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_model_profiles(db: Session, capability: Optional[str] = None, engine_id: Optional[str] = None, enabled: Optional[bool] = None) -> list[dict[str, Any]]:
    statement = select(StudioModelCapability)
    if capability:
        statement = statement.where(StudioModelCapability.capability == capability)
    if engine_id:
        statement = statement.where(StudioModelCapability.engine_id == engine_id)
    if enabled is not None:
        statement = statement.where(StudioModelCapability.enabled.is_(enabled))
    rows = db.scalars(statement.order_by(StudioModelCapability.priority.asc(), StudioModelCapability.updated_at.desc())).all()
    return [serialize_model_profile(row) for row in rows]


def list_generation_presets(db: Session, capability: Optional[str] = None, engine_id: Optional[str] = None, enabled: Optional[bool] = None) -> list[dict[str, Any]]:
    ensure_default_generation_profiles(db)
    statement = select(StudioGenerationPreset)
    if capability:
        statement = statement.where(StudioGenerationPreset.capability == capability)
    if engine_id:
        statement = statement.where(StudioGenerationPreset.engine_id == engine_id)
    if enabled is not None:
        statement = statement.where(StudioGenerationPreset.enabled.is_(enabled))
    rows = db.scalars(statement.order_by(StudioGenerationPreset.is_default.desc(), StudioGenerationPreset.priority.asc())).all()
    return [serialize_generation_preset(row) for row in rows]


def create_or_update_generation_preset(db: Session, payload: dict[str, Any], preset_id: Optional[str] = None) -> StudioGenerationPreset:
    row = db.get(StudioGenerationPreset, preset_id) if preset_id else None
    if not row:
        row = StudioGenerationPreset(
            name=str(payload.get("name") or "").strip(),
            display_name=str(payload.get("display_name") or ""),
            capability=str(payload.get("capability") or "").strip(),
            engine_id=str(payload.get("engine_id") or "").strip(),
            parameters_json="{}",
            timeout_seconds=120,
            max_attempts=1,
            enabled=True,
            is_default=False,
            priority=100,
            remark="",
        )
        db.add(row)
    if not row.name:
        raise HTTPException(status_code=422, detail="preset name is required")
    for field in ["name", "display_name", "capability", "engine_id", "remark"]:
        if field in payload:
            setattr(row, field, str(payload.get(field) or ""))
    for field in ["model_profile_id", "workflow_profile_id", "fallback_preset_id"]:
        if field in payload:
            setattr(row, field, str(payload.get(field) or "") or None)
    if "parameters" in payload or "parameters_json" in payload:
        row.parameters_json = stable_json(payload.get("parameters") if "parameters" in payload else parse_json(payload.get("parameters_json"), {}))
    if "timeout_seconds" in payload:
        row.timeout_seconds = int(payload.get("timeout_seconds") or 120)
    if "max_attempts" in payload:
        row.max_attempts = int(payload.get("max_attempts") or 1)
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    if "is_default" in payload:
        row.is_default = bool(payload.get("is_default"))
    if "priority" in payload:
        row.priority = int(payload.get("priority") or 100)
    db.flush()
    return row


def default_preset(db: Session, capability: str) -> Optional[StudioGenerationPreset]:
    ensure_default_generation_profiles(db)
    return db.scalars(
        select(StudioGenerationPreset)
        .where(StudioGenerationPreset.capability == capability)
        .where(StudioGenerationPreset.enabled.is_(True))
        .order_by(StudioGenerationPreset.is_default.desc(), StudioGenerationPreset.priority.asc())
    ).first()


def ensure_default_generation_profiles(db: Session) -> None:
    existing = db.get(StudioGenerationPreset, DEFAULT_PRESET_ID)
    if existing:
        return
    workflow = db.scalars(
        select(StudioGenerationWorkflow)
        .where(StudioGenerationWorkflow.provider == "comfyui")
        .where(StudioGenerationWorkflow.workflow_type == "image_generation")
        .order_by(StudioGenerationWorkflow.status.desc(), StudioGenerationWorkflow.updated_at.desc())
    ).first()
    if not workflow:
        return
    if workflow.status != "available":
        workflow.status = "available"
    model = db.get(StudioModelCapability, DEFAULT_MODEL_ID)
    if not model:
        model = StudioModelCapability(
            id=DEFAULT_MODEL_ID,
            name="ComfyUI Default Image",
            display_name="ComfyUI Default Image",
            provider="comfyui",
            engine_id="comfyui",
            capability="image",
            model_type="image",
            model_identifier="comfyui-workflow-default",
            enabled=True,
            is_default=True,
            priority=100,
            status="available",
            supported_widths_json=stable_json([512, 768, 1024]),
            supported_heights_json=stable_json([512, 768, 1024]),
            supported_aspect_ratios_json=stable_json(["1:1", "9:16", "16:9"]),
            default_parameters_json=stable_json({"width": 768, "height": 1024}),
            metadata_json="{}",
        )
        db.add(model)
        db.flush()
    default = StudioGenerationPreset(
        id=DEFAULT_PRESET_ID,
        name="image_scene_default",
        display_name="Image Scene Default",
        capability="image",
        engine_id="comfyui",
        model_profile_id=model.id,
        workflow_profile_id=workflow.id,
        parameters_json=stable_json({"width": 768, "height": 1024, "aspect_ratio": "9:16"}),
        timeout_seconds=120,
        max_attempts=1,
        enabled=True,
        is_default=True,
        priority=100,
        fallback_preset_id=FAST_PRESET_ID,
        remark="Default local image preset for scene generation.",
    )
    fast = StudioGenerationPreset(
        id=FAST_PRESET_ID,
        name="image_scene_fast",
        display_name="Image Scene Fast",
        capability="image",
        engine_id="comfyui",
        model_profile_id=model.id,
        workflow_profile_id=workflow.id,
        parameters_json=stable_json({"width": 512, "height": 768, "aspect_ratio": "9:16", "quality": "fast"}),
        timeout_seconds=90,
        max_attempts=1,
        enabled=True,
        is_default=False,
        priority=200,
        remark="Lower-resource fallback image preset.",
    )
    db.add_all([default, fast])
    db.flush()


def resolve_preset(db: Session, task_type: str, preset_id: Optional[str] = None) -> StudioGenerationPreset:
    capability = capability_for_task_type(task_type)
    row = db.get(StudioGenerationPreset, preset_id) if preset_id else default_preset(db, capability)
    if not row:
        raise HTTPException(status_code=422, detail=f"generation preset not found for capability: {capability}")
    if not row.enabled:
        raise HTTPException(status_code=422, detail="generation preset is disabled")
    return row


def preset_for_workflow(db: Session, workflow_id: str, task_type: str) -> StudioGenerationPreset:
    workflow = db.get(StudioGenerationWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    capability = capability_for_task_type(task_type)
    existing = db.scalars(
        select(StudioGenerationPreset)
        .where(StudioGenerationPreset.workflow_profile_id == workflow.id)
        .where(StudioGenerationPreset.capability == capability)
        .order_by(StudioGenerationPreset.updated_at.desc())
    ).first()
    if existing:
        return existing
    model = db.scalars(
        select(StudioModelCapability)
        .where(StudioModelCapability.engine_id == workflow.provider)
        .where(StudioModelCapability.capability == capability)
        .where(StudioModelCapability.enabled.is_(True))
        .order_by(StudioModelCapability.is_default.desc(), StudioModelCapability.priority.asc())
    ).first()
    row = StudioGenerationPreset(
        name=f"workflow_{workflow.id[:8]}_{capability}",
        display_name=f"Workflow {workflow.name}",
        capability=capability,
        engine_id=workflow.provider,
        model_profile_id=model.id if model else None,
        workflow_profile_id=workflow.id,
        parameters_json=stable_json({"width": 768, "height": 1024} if capability == "image" else {}),
        timeout_seconds=120,
        max_attempts=1,
        enabled=True,
        is_default=False,
        priority=500,
        remark="Auto-created compatibility preset for workflow_id based generation.",
    )
    db.add(row)
    db.flush()
    return row


def safe_json_paths(model: Optional[StudioModelCapability], workflow: Optional[StudioGenerationWorkflow]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if model:
        for field, value in {
            "workflow_path": model.workflow_path,
            "checkpoint_path": model.checkpoint_path,
            "vae_path": model.vae_path,
        }.items():
            check_path_safe(value, field, checks)
        for index, path in enumerate(parse_json(model.lora_paths_json, [])):
            check_path_safe(str(path), f"lora_paths[{index}]", checks)
    if workflow:
        check_path_safe(workflow.workflow_path, "workflow_path", checks)
    return checks


def preflight_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" and check.get("blocking") for check in checks):
        return "failed"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    if any(check["status"] == "unknown" for check in checks):
        return "unknown"
    return "passed"


def add_check(checks: list[dict[str, Any]], code: str, status: str, message: str, blocking: bool, details: Optional[dict[str, Any]] = None) -> None:
    checks.append(
        {
            "code": code,
            "status": status,
            "message": message,
            "details": details or {},
            "blocking": blocking,
        }
    )


def disk_free_gb(path: str) -> Optional[float]:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / 1024**3, 2)
    except Exception:
        return None


def available_vram_gb() -> Optional[float]:
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        first = result.stdout.strip().splitlines()[0].strip()
        return round(float(first) / 1024, 2)
    except Exception:
        return None


def build_config_snapshot(
    preset: StudioGenerationPreset,
    model: Optional[StudioModelCapability],
    workflow: Optional[StudioGenerationWorkflow],
    parameters: Optional[dict[str, Any]] = None,
    fallback_used: bool = False,
    fallback_from_preset_id: Optional[str] = None,
) -> dict[str, Any]:
    model_defaults = parse_json(model.default_parameters_json, {}) if model else {}
    preset_parameters = parse_json(preset.parameters_json, {})
    resolved = {**model_defaults, **preset_parameters, **(parameters or {})}
    return {
        "configuration_version": CONFIGURATION_VERSION,
        "capability": preset.capability,
        "engine_id": preset.engine_id,
        "preset_id": preset.id,
        "preset_name": preset.name,
        "model_profile_id": model.id if model else None,
        "model_name": model.name if model else "",
        "workflow_profile_id": workflow.id if workflow else None,
        "workflow_name": workflow.name if workflow else "",
        "resolved_parameters": resolved,
        "fallback_used": fallback_used,
        "fallback_from_preset_id": fallback_from_preset_id,
        "fallback_to_preset_id": preset.id if fallback_used else None,
    }


def run_generation_preflight(
    db: Session,
    project_id: str,
    task_type: str = "image_generation",
    scene_id: Optional[str] = None,
    preset_id: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
    generation_task_id: Optional[str] = None,
    persist: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    project = db.get(StudioVideoProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    scene = db.get(StudioVideoScene, scene_id) if scene_id else None
    preset = resolve_preset(db, task_type, preset_id)
    model = db.get(StudioModelCapability, preset.model_profile_id) if preset.model_profile_id else None
    workflow = db.get(StudioGenerationWorkflow, preset.workflow_profile_id) if preset.workflow_profile_id else None
    checks: list[dict[str, Any]] = []

    try:
        engine = get_generation_engine(preset.engine_id)
    except KeyError:
        engine = None
        add_check(checks, "ENGINE_NOT_CONFIGURED", "failed", f"Engine {preset.engine_id} is not registered.", True)
    if engine:
        health = engine.health_check()
        if health.get("available"):
            add_check(checks, "ENGINE_REACHABLE", "passed", f"{preset.engine_id} is reachable.", False, health)
        else:
            code = "FFMPEG_NOT_FOUND" if preset.engine_id == "ffmpeg" else "ENGINE_UNREACHABLE"
            add_check(checks, code, "failed", str(health.get("message") or "Engine is unavailable."), True, health)

    if not model:
        add_check(checks, "MODEL_NOT_FOUND", "failed", "Model profile is missing.", True)
    else:
        if not model.enabled or model.status != "available":
            add_check(checks, "MODEL_NOT_FOUND", "failed", "Model profile is disabled or unavailable.", True, serialize_model_profile(model))
        else:
            add_check(checks, "MODEL_AVAILABLE", "passed", "Model profile is available.", False, {"model": model.name})

    if not workflow:
        add_check(checks, "WORKFLOW_NOT_FOUND", "failed", "Workflow profile is missing.", True)
    else:
        if not workflow.enabled or workflow.status != "available":
            add_check(checks, "WORKFLOW_NOT_FOUND", "failed", "Workflow profile is disabled or unavailable.", True)
        else:
            try:
                validate_workflow(workflow.provider, workflow.workflow_type, parse_json(workflow.workflow_json, {}))
                add_check(checks, "WORKFLOW_VALID", "passed", "Workflow JSON is valid.", False)
            except Exception as exc:
                add_check(checks, "WORKFLOW_INVALID", "failed", str(exc), True)
            for item in parse_json(workflow.required_models_json, []):
                if not isinstance(item, dict):
                    continue
                required_name = str(item.get("name") or "").strip()
                required_type = str(item.get("type") or item.get("model_type") or "").strip()
                if not required_name:
                    continue
                statement = select(StudioModelCapability).where(StudioModelCapability.provider == workflow.provider).where(StudioModelCapability.name == required_name)
                if required_type:
                    statement = statement.where(StudioModelCapability.model_type == required_type)
                required = db.scalars(statement.where(StudioModelCapability.status == "available")).first()
                if not required:
                    add_check(checks, "MODEL_NOT_FOUND", "failed", f"Required model is missing: {required_name}", True, {"model": required_name})

    checks.extend(safe_json_paths(model, workflow))

    for root_name, root in {
        "output": settings.studio_output_root,
        "temp": settings.studio_temp_root,
    }.items():
        check_path_safe(root, f"{root_name}_root", checks)
        path = Path(root)
        if path.exists() and os.access(path, os.W_OK):
            add_check(checks, "OUTPUT_DIRECTORY_WRITABLE", "passed", f"{root_name} directory is writable.", False, {"path": str(path)})
        elif path.exists():
            add_check(checks, "OUTPUT_DIRECTORY_UNWRITABLE", "failed", f"{root_name} directory is not writable.", True, {"path": str(path)})
        else:
            add_check(checks, "OUTPUT_DIRECTORY_UNWRITABLE", "warning", f"{root_name} directory does not exist yet.", False, {"path": str(path)})

    free_gb = disk_free_gb(settings.studio_storage_root)
    if free_gb is None:
        add_check(checks, "INSUFFICIENT_DISK_SPACE", "unknown", "Disk free space could not be detected.", False)
    elif free_gb < settings.studio_min_free_disk_gb:
        add_check(checks, "INSUFFICIENT_DISK_SPACE", "failed", "Not enough free disk space.", True, {"free_gb": free_gb})
    else:
        add_check(checks, "DISK_SPACE_OK", "passed", "Free disk space is sufficient.", False, {"free_gb": free_gb})

    snapshot = build_config_snapshot(preset, model, workflow, parameters)
    resolved = snapshot["resolved_parameters"]
    if scene and not (scene.image_prompt or scene.visual_prompt or scene.visual_description):
        add_check(checks, "INVALID_GENERATION_CONFIG", "failed", "Scene prompt is empty.", True)
    if preset.capability == "image":
        width = resolved.get("width")
        height = resolved.get("height")
        if model and width and parse_json(model.supported_widths_json, []) and int(width) not in parse_json(model.supported_widths_json, []):
            add_check(checks, "UNSUPPORTED_RESOLUTION", "failed", "Width is not supported by model profile.", True, {"width": width})
        if model and height and parse_json(model.supported_heights_json, []) and int(height) not in parse_json(model.supported_heights_json, []):
            add_check(checks, "UNSUPPORTED_RESOLUTION", "failed", "Height is not supported by model profile.", True, {"height": height})
    if preset.capability == "video":
        duration = resolved.get("duration")
        fps = resolved.get("fps")
        if model and duration and parse_json(model.supported_durations_json, []) and int(duration) not in parse_json(model.supported_durations_json, []):
            add_check(checks, "UNSUPPORTED_DURATION", "failed", "Duration is not supported by model profile.", True, {"duration": duration})
        if model and fps and parse_json(model.supported_fps_json, []) and int(fps) not in parse_json(model.supported_fps_json, []):
            add_check(checks, "UNSUPPORTED_FPS", "failed", "FPS is not supported by model profile.", True, {"fps": fps})

    estimated_vram = model.estimated_vram_gb if model else None
    free_vram = available_vram_gb()
    if estimated_vram and free_vram is not None and estimated_vram > free_vram:
        add_check(checks, "INSUFFICIENT_VRAM", "failed", "Estimated VRAM exceeds available VRAM.", True, {"estimated_vram_gb": estimated_vram, "available_vram_gb": free_vram})
    elif estimated_vram and free_vram is None:
        add_check(checks, "GPU_NOT_FOUND", "unknown", "GPU or VRAM could not be detected.", False, {"estimated_vram_gb": estimated_vram})

    status = preflight_status(checks)
    result = {
        "status": status,
        "checks": checks,
        "checked_at": utc_now().isoformat(),
        "engine_id": preset.engine_id,
        "preset_id": preset.id,
        "configuration_snapshot": snapshot,
    }
    if persist:
        row = StudioPreflightResult(
            generation_task_id=generation_task_id,
            video_project_id=project.id,
            scene_id=scene.id if scene else None,
            engine_id=preset.engine_id,
            preset_id=preset.id,
            status=status,
            checks_json=stable_json(checks),
            result_json=stable_json(result),
        )
        db.add(row)
        task = db.get(StudioGenerationTask, generation_task_id) if generation_task_id else None
        if task:
            task.preflight_result_json = stable_json(result)
        db.flush()
    return result


def blocking_failure(preflight: dict[str, Any]) -> bool:
    return any(check.get("status") == "failed" and check.get("blocking") for check in preflight.get("checks") or [])


def resolve_with_optional_fallback(
    db: Session,
    project_id: str,
    task_type: str,
    scene_id: Optional[str] = None,
    preset_id: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
) -> tuple[StudioGenerationPreset, dict[str, Any], bool, Optional[str]]:
    settings = get_settings()
    primary = resolve_preset(db, task_type, preset_id)
    primary_result = run_generation_preflight(db, project_id, task_type, scene_id, primary.id, parameters, persist=False)
    if not blocking_failure(primary_result) or not settings.studio_allow_preset_fallback:
        return primary, primary_result, False, None
    candidates = db.scalars(
        select(StudioGenerationPreset)
        .where(StudioGenerationPreset.capability == primary.capability)
        .where(StudioGenerationPreset.enabled.is_(True))
        .where(StudioGenerationPreset.id != primary.id)
        .order_by(StudioGenerationPreset.priority.asc())
    ).all()
    for candidate in candidates:
        result = run_generation_preflight(db, project_id, task_type, scene_id, candidate.id, parameters, persist=False)
        if not blocking_failure(result):
            result["fallback_used"] = True
            result["fallback_from_preset_id"] = primary.id
            result["fallback_to_preset_id"] = candidate.id
            return candidate, result, True, primary.id
    return primary, primary_result, False, None


def save_generation_snapshot(
    db: Session,
    task: StudioGenerationTask,
    preset: StudioGenerationPreset,
    preflight: dict[str, Any],
    fallback_used: bool = False,
    fallback_from_preset_id: Optional[str] = None,
) -> dict[str, Any]:
    model = db.get(StudioModelCapability, preset.model_profile_id) if preset.model_profile_id else None
    workflow = db.get(StudioGenerationWorkflow, preset.workflow_profile_id) if preset.workflow_profile_id else None
    snapshot = build_config_snapshot(
        preset,
        model,
        workflow,
        preflight.get("configuration_snapshot", {}).get("resolved_parameters") or {},
        fallback_used=fallback_used,
        fallback_from_preset_id=fallback_from_preset_id,
    )
    row = StudioGenerationConfigSnapshot(
        generation_task_id=task.id,
        video_project_id=task.video_project_id,
        scene_id=task.scene_id,
        capability=preset.capability,
        engine_id=preset.engine_id,
        preset_id=preset.id,
        model_profile_id=preset.model_profile_id,
        workflow_profile_id=preset.workflow_profile_id,
        snapshot_json=stable_json(snapshot),
        configuration_version=CONFIGURATION_VERSION,
        fallback_used=fallback_used,
        fallback_from_preset_id=fallback_from_preset_id,
        fallback_to_preset_id=preset.id if fallback_used else None,
    )
    db.add(row)
    task.preset_id = preset.id
    task.engine_id = preset.engine_id
    task.model_profile_id = preset.model_profile_id
    task.workflow_profile_id = preset.workflow_profile_id
    task.provider = preset.engine_id
    task.provider_name = preset.engine_id
    task.configuration_version = CONFIGURATION_VERSION
    task.configuration_snapshot_json = stable_json(snapshot)
    task.preflight_result_json = stable_json(preflight)
    task.fallback_used = fallback_used
    context = parse_json(task.context_json, {})
    context.update(
        {
            "preset_id": preset.id,
            "workflow_id": preset.workflow_profile_id,
            "model_profile_id": preset.model_profile_id,
            "engine_id": preset.engine_id,
            "configuration_snapshot_id": row.id,
        }
    )
    task.context_json = stable_json(context)
    db.flush()
    return snapshot


def prepare_task_generation_config(
    db: Session,
    task: StudioGenerationTask,
    preset_id: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if task.configuration_snapshot_json and parse_json(task.configuration_snapshot_json, {}):
        return parse_json(task.configuration_snapshot_json, {})
    if not preset_id and task.workflow_profile_id:
        preset_id = preset_for_workflow(db, task.workflow_profile_id, task.task_type).id
    preset, preflight, fallback_used, fallback_from = resolve_with_optional_fallback(
        db,
        task.video_project_id,
        task.task_type,
        task.scene_id,
        preset_id or task.preset_id,
        parameters,
    )
    if blocking_failure(preflight):
        task.preflight_result_json = stable_json(preflight)
        task.error_message = "Preflight failed: " + ", ".join(
            check["code"] for check in preflight.get("checks", []) if check.get("status") == "failed" and check.get("blocking")
        )
        db.flush()
        raise HTTPException(status_code=409, detail=task.error_message)
    return save_generation_snapshot(db, task, preset, preflight, fallback_used, fallback_from)


def latest_task_generation_config(db: Session, task: StudioGenerationTask) -> dict[str, Any]:
    snapshot = parse_json(task.configuration_snapshot_json, {})
    preflight = parse_json(task.preflight_result_json, {})
    if not snapshot:
        snapshot = {"configuration_version": "legacy", "engine_id": task.provider_name or task.provider, "preset_id": task.preset_id}
    return {"snapshot": snapshot, "preflight": preflight}


def job_generation_config(db: Session, project_id: str) -> dict[str, Any]:
    tasks = db.scalars(
        select(StudioGenerationTask)
        .where(StudioGenerationTask.video_project_id == project_id)
        .order_by(StudioGenerationTask.created_at.asc())
    ).all()
    return {"items": [latest_task_generation_config(db, task) | {"task_id": task.id, "task_type": task.task_type} for task in tasks]}


def retry_with_config(db: Session, project_id: str, preset_id: str, from_step: str = "") -> dict[str, Any]:
    tasks = db.scalars(
        select(StudioGenerationTask)
        .where(StudioGenerationTask.video_project_id == project_id)
        .where(StudioGenerationTask.status == "failed")
        .order_by(StudioGenerationTask.updated_at.desc())
    ).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="failed generation task not found")
    task = tasks[0]
    task.preset_id = preset_id
    task.configuration_snapshot_json = "{}"
    task.preflight_result_json = "{}"
    if from_step:
        task.failed_step = from_step
    task.retry_count += 1
    db.flush()
    return {"task_id": task.id, "retry_count": task.retry_count, "preset_id": preset_id}


def generation_engines_payload() -> dict[str, Any]:
    return {"items": list_generation_engines()}
