from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class EditorialScene(BaseModel):
    scene_number: int
    duration: float
    visual_prompt: str
    voiceover: str
    subtitle: str
    camera_direction: str = ""


class EditorialBriefOutput(BaseModel):
    title: str
    hook: str
    target_audience: str = ""
    script: str
    scenes: list[EditorialScene] = Field(default_factory=list)
    caption: str
    hashtags: list[str] = Field(default_factory=list)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def validate_editorial_brief_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text or "")
    except Exception as exc:
        raise ValueError(f"GPT Output JSON 不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GPT Output JSON 必须是对象")
    required = ["title", "hook", "script", "scenes", "caption"]
    for field in required:
        if field not in value:
            raise ValueError(f"缺少 {field} 字段")
    if not isinstance(value.get("scenes"), list) or not value["scenes"]:
        raise ValueError("scenes 字段不能为空")
    for index, scene in enumerate(value["scenes"], start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"第 {index} 个 scene 必须是对象")
        for field in ["scene_number", "duration", "visual_prompt", "voiceover", "subtitle"]:
            if field not in scene:
                raise ValueError(f"第 {index} 个 scene 缺少 {field} 字段")
    return model_to_dict(EditorialBriefOutput(**value))
