from __future__ import annotations

from typing import Any

from services.generation.providers.base import GenerationProvider, PlaceholderGenerationProvider
from services.generation.providers.comfyui.provider import ComfyUIProvider


PROVIDER_NAMES = ["comfyui", "flux", "wan", "tts", "ffmpeg", "kling", "runway", "veo"]


def _build_registry() -> dict[str, GenerationProvider]:
    registry: dict[str, GenerationProvider] = {name: PlaceholderGenerationProvider(name) for name in PROVIDER_NAMES}
    registry["comfyui"] = ComfyUIProvider()
    return registry


_REGISTRY = _build_registry()


def list_generation_providers() -> list[dict[str, Any]]:
    return [provider.health_check() for provider in _REGISTRY.values()]


def get_generation_provider(name: str) -> GenerationProvider:
    normalized = (name or "").strip().lower()
    if normalized not in _REGISTRY:
        raise KeyError(f"generation provider not found: {name}")
    return _REGISTRY[normalized]


def provider_available(name: str) -> bool:
    return bool(get_generation_provider(name).health_check().get("available"))


def provider_health(name: str) -> dict[str, Any]:
    return get_generation_provider(name).health_check()
