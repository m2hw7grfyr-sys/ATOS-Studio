from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from config.settings import get_settings
from services.generation.providers.base import GenerationProvider


class ComfyUIProvider(GenerationProvider):
    provider_name = "comfyui"
    provider_type = "local_http"

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: Optional[float] = None, enabled: Optional[bool] = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.comfyui_effective_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds if timeout_seconds is not None else settings.comfyui_timeout_seconds)
        self.enabled = bool(settings.comfyui_enabled if enabled is None else enabled)

    def _request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("ComfyUI provider is disabled")
        if not self.base_url:
            raise RuntimeError("ComfyUI URL is not configured")
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"ComfyUI HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ComfyUI unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("ComfyUI request timed out") from exc

    def health_check(self) -> dict[str, Any]:
        if not self.base_url:
            return {
                "provider": self.provider_name,
                "provider_type": self.provider_type,
                "available": False,
                "status": "not_configured",
                "message": "ComfyUI URL is not configured.",
            }
        if not self.enabled:
            return {
                "provider": self.provider_name,
                "provider_type": self.provider_type,
                "available": False,
                "status": "disabled",
                "message": "ComfyUI is disabled by COMFYUI_ENABLED=false.",
            }
        try:
            payload = self._request("GET", "/system_stats")
            return {
                "provider": self.provider_name,
                "provider_type": self.provider_type,
                "available": True,
                "status": "available",
                "message": "ComfyUI system_stats is reachable.",
                "details": payload,
            }
        except Exception as exc:
            return {
                "provider": self.provider_name,
                "provider_type": self.provider_type,
                "available": False,
                "status": "unavailable",
                "message": str(exc),
            }

    def submit_job(self, workflow: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prompt = workflow.get("prompt") if isinstance(workflow.get("prompt"), dict) else workflow
        if "{{visual_prompt}}" in json.dumps(prompt, ensure_ascii=False):
            prompt = json.loads(json.dumps(prompt, ensure_ascii=False).replace("{{visual_prompt}}", str(context.get("visual_prompt") or "")))
        payload = self._request("POST", "/prompt", {"prompt": prompt})
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        return {"provider_task_id": prompt_id, "raw_response": payload}

    def get_status(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        if not provider_task_id:
            return {"provider": self.provider_name, "provider_task_id": provider_task_id, "status": "missing"}
        payload = self._request("GET", f"/history/{urllib.parse.quote(provider_task_id)}")
        history = payload.get(provider_task_id) if isinstance(payload, dict) else None
        if not history:
            return {"provider": self.provider_name, "provider_task_id": provider_task_id, "status": "running"}
        status = history.get("status") or {}
        completed = bool(status.get("completed"))
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "status": "completed" if completed else "running",
            "raw_response": history,
        }

    def get_result(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        deadline = time.time() + max(self.timeout_seconds, 1)
        status = self.get_status(provider_task_id)
        while status.get("status") == "running" and time.time() < deadline:
            time.sleep(1)
            status = self.get_status(provider_task_id)
        history = status.get("raw_response") or {}
        assets = []
        outputs = history.get("outputs") or {}
        for output in outputs.values():
            for image in output.get("images") or []:
                filename = image.get("filename")
                if not filename:
                    continue
                image_type = image.get("type") or "output"
                subfolder = image.get("subfolder") or ""
                file_path = "/".join(part for part in [image_type, subfolder, filename] if part)
                query = urllib.parse.urlencode(
                    {
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": image_type,
                    }
                )
                assets.append(
                    {
                        "asset_type": "image",
                        "file_path": file_path,
                        "url": f"{self.base_url}/view?{query}",
                        "metadata": image,
                    }
                )
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "status": "completed" if assets else status.get("status", "running"),
            "assets": assets,
            "raw_response": history,
        }

    def cancel(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "cancelled": False,
            "message": "ComfyUI cancel is reserved for a later sprint.",
        }
