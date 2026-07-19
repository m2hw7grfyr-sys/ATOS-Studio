from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.production import (
    StudioGenerationPipeline,
    StudioGenerationTask,
    StudioVideoProject,
    StudioVideoScene,
)
from repositories.content_items import stable_json
from services.video_production import (
    GENERATION_TASK_TYPES,
    serialize_generation_pipeline,
    serialize_generation_task,
)


DEFAULT_PROVIDER_NAME = "mock"


def generation_context(project: StudioVideoProject, scene: Optional[StudioVideoScene] = None) -> dict[str, Any]:
    return {
        "topic_package_id": project.topic_package_id,
        "editorial_brief_id": project.editorial_brief_id,
        "video_project_id": project.id,
        "persona_id": project.persona_id,
        "social_account_id": project.social_account_id,
        "scene_id": scene.id if scene else None,
    }


def _new_task(
    project: StudioVideoProject,
    task_type: str,
    scene: Optional[StudioVideoScene] = None,
    depends_on_task_id: Optional[str] = None,
    provider_name: str = DEFAULT_PROVIDER_NAME,
) -> StudioGenerationTask:
    if task_type not in GENERATION_TASK_TYPES:
        raise HTTPException(status_code=422, detail=f"unsupported generation task type: {task_type}")
    context = generation_context(project, scene)
    return StudioGenerationTask(
        video_project_id=project.id,
        scene_id=scene.id if scene else None,
        task_type=task_type,
        provider=provider_name,
        provider_name=provider_name,
        status="queued",
        priority=project.priority or "normal",
        max_retry=3,
        depends_on_task_id=depends_on_task_id,
        context_json=stable_json(context),
        input_json=stable_json({"context": context}),
        output_json="{}",
    )


def create_generation_plan(db: Session, video_project_id: str) -> dict[str, Any]:
    project = db.get(StudioVideoProject, video_project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    scenes = db.scalars(
        select(StudioVideoScene)
        .where(StudioVideoScene.video_project_id == project.id)
        .order_by(StudioVideoScene.scene_number.asc())
    ).all()
    pipeline = StudioGenerationPipeline(
        video_project_id=project.id,
        status="planning",
        current_stage="planning",
        total_tasks=0,
        completed_tasks=0,
    )
    db.add(pipeline)
    db.flush()

    tasks: list[StudioGenerationTask] = []
    last_scene_task_id: Optional[str] = None
    for scene in scenes:
        image_task = _new_task(project, "image_generation", scene=scene)
        db.add(image_task)
        db.flush()
        tasks.append(image_task)

        video_task = _new_task(project, "video_generation", scene=scene, depends_on_task_id=image_task.id)
        db.add(video_task)
        db.flush()
        tasks.append(video_task)
        last_scene_task_id = video_task.id

    voice_task = _new_task(project, "voice_generation", depends_on_task_id=last_scene_task_id)
    db.add(voice_task)
    db.flush()
    tasks.append(voice_task)

    subtitle_task = _new_task(project, "subtitle_generation", depends_on_task_id=voice_task.id)
    db.add(subtitle_task)
    db.flush()
    tasks.append(subtitle_task)

    composition_task = _new_task(project, "composition", depends_on_task_id=subtitle_task.id)
    db.add(composition_task)
    db.flush()
    tasks.append(composition_task)

    pipeline.status = "queued"
    pipeline.current_stage = "tasks_created"
    pipeline.total_tasks = len(tasks)
    project.status = "planning"
    db.flush()
    return {
        "pipeline": serialize_generation_pipeline(pipeline),
        "tasks": [serialize_generation_task(task) for task in tasks],
    }


def list_generation_pipelines(db: Session, video_project_id: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(StudioGenerationPipeline)
    if video_project_id:
        statement = statement.where(StudioGenerationPipeline.video_project_id == video_project_id)
    rows = db.scalars(statement.order_by(StudioGenerationPipeline.created_at.desc())).all()
    return [serialize_generation_pipeline(row) for row in rows]


def list_generation_tasks(
    db: Session,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    provider: Optional[str] = None,
) -> list[dict[str, Any]]:
    statement = select(StudioGenerationTask)
    if status:
        statement = statement.where(StudioGenerationTask.status == status)
    if task_type:
        statement = statement.where(StudioGenerationTask.task_type == task_type)
    if provider:
        statement = statement.where(StudioGenerationTask.provider_name == provider)
    rows = db.scalars(statement.order_by(StudioGenerationTask.updated_at.desc())).all()
    return [serialize_generation_task(row) for row in rows]
