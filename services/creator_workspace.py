from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.ai import StudioEditorialBrief
from models.content_item import utc_now
from models.production import StudioVideoProject, StudioVideoScene
from repositories.content_items import parse_json, stable_json
from services.video_production import serialize_video_project, serialize_video_scene


EDITORIAL_FIELDS = {
    "content_goal",
    "main_angle",
    "hook",
    "core_message",
    "call_to_action",
    "tone",
    "platform",
    "target_duration",
}

SCENE_FIELDS = {
    "title",
    "purpose",
    "visual_description",
    "voiceover",
    "on_screen_text",
    "image_prompt",
    "video_prompt",
    "negative_prompt",
    "camera_direction",
    "status",
}


def get_creator_workspace_project(db: Session, project_id: str) -> dict[str, Any]:
    row = db.get(StudioVideoProject, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="video project not found")
    return serialize_video_project(db, row, include_detail=True)


def update_editorial_workspace(db: Session, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    project = db.get(StudioVideoProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    brief = db.get(StudioEditorialBrief, project.editorial_brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="editorial brief not found")
    output = parse_json(brief.output_json, {}) or parse_json(brief.input_json, {})
    for field in EDITORIAL_FIELDS:
        if field in payload:
            output[field] = str(payload.get(field) or "")
    if "target_duration" in output:
        raw_duration = str(output.get("target_duration") or "").strip()
        if raw_duration.isdigit():
            project.duration_target = int(raw_duration)
    brief.output_json = stable_json(output)
    brief.updated_at = utc_now()
    project.description = str(output.get("core_message") or output.get("hook") or project.description or "")
    project.updated_at = utc_now()
    db.flush()
    return output


def ordered_scenes(db: Session, project_id: str) -> list[StudioVideoScene]:
    return db.scalars(
        select(StudioVideoScene)
        .where(StudioVideoScene.video_project_id == project_id)
        .order_by(StudioVideoScene.scene_number.asc(), StudioVideoScene.created_at.asc())
    ).all()


def renumber_scenes(db: Session, project_id: str) -> None:
    for index, scene in enumerate(ordered_scenes(db, project_id), start=1):
        scene.scene_number = index
        scene.updated_at = utc_now()
    db.flush()


def create_scene(db: Session, project_id: str) -> StudioVideoScene:
    project = db.get(StudioVideoProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="video project not found")
    count = len(ordered_scenes(db, project_id))
    scene = StudioVideoScene(
        video_project_id=project_id,
        scene_number=count + 1,
        title=f"Scene {count + 1}",
        status="draft",
    )
    db.add(scene)
    project.updated_at = utc_now()
    db.flush()
    return scene


def update_scene(db: Session, scene_id: str, payload: dict[str, Any]) -> StudioVideoScene:
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    for field in SCENE_FIELDS:
        if field in payload:
            setattr(scene, field, str(payload.get(field) or ""))
    if "duration" in payload:
        raw_duration = str(payload.get("duration") or "").strip()
        scene.duration = float(raw_duration) if raw_duration else None
    if "visual_prompt" in payload:
        scene.visual_prompt = str(payload.get("visual_prompt") or "")
    else:
        scene.visual_prompt = scene.image_prompt or scene.visual_description or scene.visual_prompt
    if "subtitle" in payload:
        scene.subtitle = str(payload.get("subtitle") or "")
    else:
        scene.subtitle = scene.on_screen_text or scene.subtitle
    scene.updated_at = utc_now()
    project = db.get(StudioVideoProject, scene.video_project_id)
    if project:
        project.updated_at = utc_now()
    db.flush()
    return scene


def copy_scene(db: Session, scene_id: str) -> StudioVideoScene:
    source = db.get(StudioVideoScene, scene_id)
    if not source:
        raise HTTPException(status_code=404, detail="scene not found")
    for scene in ordered_scenes(db, source.video_project_id):
        if scene.scene_number > source.scene_number:
            scene.scene_number += 1
    copied = StudioVideoScene(
        video_project_id=source.video_project_id,
        scene_number=source.scene_number + 1,
        title=f"{source.title or 'Scene'} Copy",
        purpose=source.purpose,
        duration=source.duration,
        visual_description=source.visual_description,
        visual_prompt=source.visual_prompt,
        image_prompt=source.image_prompt,
        video_prompt=source.video_prompt,
        negative_prompt=source.negative_prompt,
        voiceover=source.voiceover,
        subtitle=source.subtitle,
        on_screen_text=source.on_screen_text,
        camera_direction=source.camera_direction,
        status="draft",
    )
    db.add(copied)
    db.flush()
    renumber_scenes(db, source.video_project_id)
    return copied


def delete_scene(db: Session, scene_id: str) -> str:
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    project_id = scene.video_project_id
    db.delete(scene)
    db.flush()
    renumber_scenes(db, project_id)
    return project_id


def move_scene(db: Session, scene_id: str, direction: str) -> Optional[StudioVideoScene]:
    scene = db.get(StudioVideoScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    scenes = ordered_scenes(db, scene.video_project_id)
    index = next((idx for idx, row in enumerate(scenes) if row.id == scene.id), None)
    if index is None:
        return scene
    target_index = index - 1 if direction == "up" else index + 1
    if target_index < 0 or target_index >= len(scenes):
        return scene
    target = scenes[target_index]
    scene.scene_number, target.scene_number = target.scene_number, scene.scene_number
    scene.updated_at = utc_now()
    target.updated_at = utc_now()
    db.flush()
    renumber_scenes(db, scene.video_project_id)
    return scene


def scene_plain_text(scene: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Scene {scene.get('scene_number')}: {scene.get('title') or ''}",
            f"Purpose: {scene.get('purpose') or ''}",
            f"Duration: {scene.get('duration') or ''}",
            f"Visual Description: {scene.get('visual_description') or scene.get('visual_prompt') or ''}",
            f"Voiceover Script: {scene.get('voiceover') or ''}",
            f"On-screen Text: {scene.get('on_screen_text') or scene.get('subtitle') or ''}",
            f"Image Prompt: {scene.get('image_prompt') or scene.get('visual_prompt') or ''}",
            f"Video Prompt: {scene.get('video_prompt') or ''}",
            f"Negative Prompt: {scene.get('negative_prompt') or ''}",
            f"Camera Direction: {scene.get('camera_direction') or ''}",
        ]
    )


def serialize_scene_for_api(row: StudioVideoScene) -> dict[str, Any]:
    return serialize_video_scene(row)
