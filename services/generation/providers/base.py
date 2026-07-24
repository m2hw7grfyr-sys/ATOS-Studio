from __future__ import annotations

from typing import Any, Optional


class GenerationProvider:
    provider_name = "base"
    provider_type = "placeholder"
    display_name = "Base Engine"
    capabilities: list[str] = []
    enabled = True

    def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("generation provider is not configured")

    def submit_job(self, workflow: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("generation provider is not configured")

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "engine_id": self.provider_name,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "enabled": self.enabled,
            "provider_type": self.provider_type,
            "available": False,
            "status": "not_configured",
            "message": "Provider adapter scaffold exists, but no runtime is connected.",
        }

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"valid": True, "warnings": [], "errors": []}

    def estimate_requirements(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"estimated_vram_gb": request.get("estimated_vram_gb"), "status": "unknown"}

    def get_status(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "status": "unknown",
        }

    def get_result(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "status": "unknown",
            "assets": [],
        }

    def cancel(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "cancelled": False,
            "message": "Provider is not configured.",
        }


class PlaceholderGenerationProvider(GenerationProvider):
    def __init__(self, provider_name: str, provider_type: str = "placeholder", capabilities: Optional[list[str]] = None, display_name: Optional[str] = None) -> None:
        self.provider_name = provider_name
        self.provider_type = provider_type
        self.capabilities = capabilities or []
        self.display_name = display_name or provider_name
