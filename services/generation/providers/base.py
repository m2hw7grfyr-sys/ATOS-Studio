from __future__ import annotations

from typing import Any, Optional


class GenerationProvider:
    provider_name = "base"
    provider_type = "placeholder"

    def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("generation provider is not configured")

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_type": self.provider_type,
            "available": False,
            "status": "not_configured",
            "message": "Provider adapter scaffold exists, but no runtime is connected.",
        }

    def get_status(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "status": "unknown",
        }

    def cancel(self, provider_task_id: Optional[str]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_task_id": provider_task_id,
            "cancelled": False,
            "message": "Provider is not configured.",
        }


class PlaceholderGenerationProvider(GenerationProvider):
    def __init__(self, provider_name: str, provider_type: str = "placeholder") -> None:
        self.provider_name = provider_name
        self.provider_type = provider_type
