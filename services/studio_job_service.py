from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.ai import StudioEditorialBrief
from models.content_item import utc_now
from models.production import StudioGenerationTask, StudioVideoProject, StudioVideoScene
from models.topic_package import StudioTopicPackage, StudioTopicPackageItem
from repositories.content_items import parse_json, stable_json
from schemas.editorial_brief import validate_editorial_brief_json
from services.generation_planner import create_generation_plan
from services.generation_executor import create_scene_image_task
from services.topic_packages import serialize_topic_package
from services.video_production import serialize_generation_task, serialize_video_project


REVIEW_STATUSES = {"draft", "pending_review", "approved", "rejected"}
JOB_FILTERS = {
    "draft": {"review_status": "draft"},
    "待编辑": {"review_status": "draft"},
    "pending_review": {"review_status": "pending_review"},
    "待审核": {"review_status": "pending_review"},
    "approved": {"review_status": "approved"},
    "审核通过": {"review_status": "approved"},
    "rejected": {"review_status": "rejected"},
    "生成中": {"status": "running"},
    "running": {"status": "running"},
    "completed": {"status": "completed"},
    "已完成": {"status": "completed"},
    "failed": {"status": "failed"},
    "失败": {"status": "failed"},
}


def safe_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def project_or_404(db: Session, project_id: str) -> StudioVideoProject:
    row = db.get(StudioVideoProject, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="studio job not found")
    return row


def editorial_brief_or_404(db: Session, project: StudioVideoProject) -> StudioEditorialBrief:
    row = db.get(StudioEditorialBrief, project.editorial_brief_id)
    if not row:
        raise HTTPException(status_code=404, detail="editorial brief not found")
    return row


def existing_editorial_json(db: Session, project: StudioVideoProject) -> str:
    if project.editorial_json_snapshot.strip():
        return project.editorial_json_snapshot
    brief = editorial_brief_or_404(db, project)
    return brief.output_json or brief.input_json or "{}"


def source_items(db: Session, topic_package_id: str) -> list[dict[str, Any]]:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        return []
    payload = serialize_topic_package(db, package, include_items=True)
    return [
        item.get("content_item")
        for item in payload.get("items") or []
        if item.get("content_item")
    ]


def final_output_status(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "not_started"
    statuses = {task.get("status") for task in tasks}
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    if statuses and statuses <= {"completed"}:
        return "completed"
    return "pending"


def generation_progress(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "0/0"
    completed = len([task for task in tasks if task.get("status") == "completed"])
    return f"{completed}/{len(tasks)}"


def serialize_studio_job(db: Session, project: StudioVideoProject, include_detail: bool = False) -> dict[str, Any]:
    project_payload = serialize_video_project(db, project, include_detail=True)
    tasks = project_payload.get("generation_tasks") or []
    package = db.get(StudioTopicPackage, project.topic_package_id)
    raw_json = existing_editorial_json(db, project)
    parsed_json = parse_json(raw_json, None)
    detail = {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "review_status": project.review_status,
        "review_note": project.review_note,
        "reviewed_at": project.reviewed_at.isoformat() if project.reviewed_at else None,
        "current_step": next((task.get("current_step") for task in tasks if task.get("status") == "running"), ""),
        "failed_step": next((task.get("failed_step") for task in tasks if task.get("failed_step")), ""),
        "retry_count": sum(int(task.get("retry_count") or 0) for task in tasks),
        "generation_progress": generation_progress(tasks),
        "final_output_status": final_output_status(tasks),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "source_title": package.title if package else "",
        "source_platform": ", ".join(sorted({item.get("source_platform", "") for item in source_items(db, project.topic_package_id)} - {""})),
        "project": project_payload,
        "editorial_json": raw_json,
        "editorial_json_parsed": parsed_json,
        "editorial_parse_error": project.editorial_parse_error,
        "generation_tasks": tasks,
    }
    if include_detail:
        detail["topic_package"] = serialize_topic_package(db, package, include_items=True) if package else None
        detail["source_items"] = source_items(db, project.topic_package_id)
        detail["scenes"] = project_payload.get("scenes") or []
    return detail


def list_studio_jobs(
    db: Session,
    status_filter: str = "",
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    statement = select(StudioVideoProject)
    mapped = JOB_FILTERS.get(status_filter or "")
    if mapped:
        if mapped.get("review_status"):
            statement = statement.where(StudioVideoProject.review_status == mapped["review_status"])
        if mapped.get("status"):
            statement = statement.where(StudioVideoProject.status == mapped["status"])
    sort_column = StudioVideoProject.created_at if sort_by == "created_at" else StudioVideoProject.updated_at
    statement = statement.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())
    rows = db.scalars(statement).all()
    return [serialize_studio_job(db, row, include_detail=False) for row in rows]


def get_studio_job(db: Session, project_id: str) -> dict[str, Any]:
    return serialize_studio_job(db, project_or_404(db, project_id), include_detail=True)


def save_editorial_json(db: Session, project_id: str, editorial_json: Any) -> dict[str, Any]:
    project = project_or_404(db, project_id)
    text = safe_json_text(editorial_json)
    try:
        json.loads(text or "{}")
    except Exception as exc:
        project.editorial_parse_error = f"GPT Output JSON 不是合法 JSON：{exc}"[:1000]
        db.flush()
        raise HTTPException(status_code=422, detail=project.editorial_parse_error) from exc
    project.editorial_json_snapshot = text
    project.editorial_parse_error = ""
    if project.review_status == "rejected":
        project.review_status = "draft"
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def rebuild_scenes_from_output(db: Session, project: StudioVideoProject, output: dict[str, Any]) -> None:
    scenes = output.get("scenes") or []
    if not scenes:
        raise HTTPException(status_code=422, detail="scenes 字段不能为空")
    existing = db.scalars(select(StudioVideoScene).where(StudioVideoScene.video_project_id == project.id)).all()
    for scene in existing:
        db.delete(scene)
    db.flush()
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise HTTPException(status_code=422, detail=f"第 {index} 个 scene 必须是对象")
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


def parse_studio_job(db: Session, project_id: str) -> dict[str, Any]:
    project = project_or_404(db, project_id)
    brief = editorial_brief_or_404(db, project)
    text = existing_editorial_json(db, project)
    try:
        parsed = validate_editorial_brief_json(text)
    except ValueError as exc:
        project.editorial_parse_error = str(exc)[:1000]
        project.updated_at = utc_now()
        db.flush()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    brief.output_json = stable_json(parsed)
    brief.input_json = stable_json(parsed)
    project.editorial_json_snapshot = stable_json(parsed)
    project.editorial_parse_error = ""
    rebuild_scenes_from_output(db, project, parsed)
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def has_valid_scenes(db: Session, project_id: str) -> bool:
    return db.scalars(select(StudioVideoScene.id).where(StudioVideoScene.video_project_id == project_id)).first() is not None


def submit_job_review(db: Session, project_id: str) -> dict[str, Any]:
    project = project_or_404(db, project_id)
    if project.review_status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="only draft or rejected jobs can be submitted for review")
    if project.editorial_parse_error:
        raise HTTPException(status_code=409, detail="cannot submit review while JSON parse error exists")
    if not has_valid_scenes(db, project.id):
        raise HTTPException(status_code=409, detail="cannot submit review without valid scenes")
    project.review_status = "pending_review"
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def approve_job(db: Session, project_id: str) -> dict[str, Any]:
    project = project_or_404(db, project_id)
    if project.review_status != "pending_review":
        raise HTTPException(status_code=409, detail="only pending_review jobs can be approved")
    if project.editorial_parse_error or not has_valid_scenes(db, project.id):
        raise HTTPException(status_code=409, detail="cannot approve job without valid parsed scenes")
    project.review_status = "approved"
    project.reviewed_at = utc_now()
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def reject_job(db: Session, project_id: str, review_note: str = "") -> dict[str, Any]:
    project = project_or_404(db, project_id)
    if project.review_status != "pending_review":
        raise HTTPException(status_code=409, detail="only pending_review jobs can be rejected")
    project.review_status = "rejected"
    project.review_note = review_note
    project.reviewed_at = utc_now()
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def start_job_generation(db: Session, project_id: str) -> dict[str, Any]:
    project = project_or_404(db, project_id)
    if project.review_status != "approved":
        raise HTTPException(status_code=409, detail="job must be approved before generation starts")
    if project.status in {"running", "completed"}:
        raise HTTPException(status_code=409, detail="job cannot be started from current status")
    if project.editorial_parse_error or not has_valid_scenes(db, project.id):
        raise HTTPException(status_code=409, detail="job requires valid parsed scenes before generation")
    existing_tasks = db.scalars(select(StudioGenerationTask).where(StudioGenerationTask.video_project_id == project.id)).all()
    if not existing_tasks:
        create_generation_plan(db, project.id)
    project.status = "running"
    project.updated_at = utc_now()
    db.flush()
    return get_studio_job(db, project_id)


def create_reviewed_scene_image_task(db: Session, scene_id: str, provider_name: str = "comfyui", workflow_id: Optional[str] = None):
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    project = project_or_404(db, scene.video_project_id)
    if project.review_status != "approved":
        raise HTTPException(status_code=409, detail="job must be approved before generation starts")
    return create_scene_image_task(db, scene_id, provider_name, workflow_id)
