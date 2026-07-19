from __future__ import annotations

import json
from typing import Any


VALID_WORKFLOW_TYPES = {"image_generation", "video_generation", "voice_generation", "composition"}
VALID_PROVIDERS = {"comfyui"}


def parse_workflow_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid workflow JSON: {exc.msg}") from exc
    else:
        raise ValueError("Invalid workflow JSON")
    if not isinstance(payload, dict):
        raise ValueError("Invalid workflow JSON: root must be object")
    return payload


def validate_workflow(provider: str, workflow_type: str, workflow_json: Any) -> dict[str, Any]:
    provider = (provider or "").strip().lower()
    workflow_type = (workflow_type or "").strip()
    if provider not in VALID_PROVIDERS:
        raise ValueError("provider mismatch or unsupported provider")
    if workflow_type not in VALID_WORKFLOW_TYPES:
        raise ValueError("unsupported workflow_type")
    payload = parse_workflow_json(workflow_json)
    if provider == "comfyui":
        prompt = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else payload
        if not isinstance(prompt, dict) or not prompt:
            raise ValueError("Missing nodes field")
        node_like_values = [value for value in prompt.values() if isinstance(value, dict)]
        if not node_like_values:
            raise ValueError("Missing nodes field")
        if not any("inputs" in value or "class_type" in value for value in node_like_values):
            raise ValueError("Missing nodes field")
    return {"valid": True, "provider": provider, "workflow_type": workflow_type, "warnings": []}
