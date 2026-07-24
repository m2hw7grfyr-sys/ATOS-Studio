from __future__ import annotations

from typing import Any

from services.generation.providers.base import GenerationProvider, PlaceholderGenerationProvider
from services.generation.providers.comfyui.provider import ComfyUIProvider
from services.generation.providers.ffmpeg.provider import FFmpegProvider


ENGINE_DEFINITIONS = {
    "comfyui": {"capabilities": ["image", "video"], "display_name": "ComfyUI"},
    "flux": {"capabilities": ["image"], "display_name": "FLUX Local"},
    "wan": {"capabilities": ["video"], "display_name": "Wan Local"},
    "local_tts": {"capabilities": ["tts"], "display_name": "Local TTS"},
    "tts": {"capabilities": ["tts"], "display_name": "Local TTS"},
    "ffmpeg": {"capabilities": ["composition"], "display_name": "FFmpeg"},
    "kling": {"capabilities": ["video"], "display_name": "Kling"},
    "runway": {"capabilities": ["video"], "display_name": "Runway"},
    "veo": {"capabilities": ["video"], "display_name": "Veo"},
}


def _build_registry() -> dict[str, GenerationProvider]:
    registry: dict[str, GenerationProvider] = {
        name: PlaceholderGenerationProvider(
            name,
            capabilities=list(definition["capabilities"]),
            display_name=str(definition["display_name"]),
        )
        for name, definition in ENGINE_DEFINITIONS.items()
    }
    registry["comfyui"] = ComfyUIProvider()
    registry["ffmpeg"] = FFmpegProvider()
    return registry


_REGISTRY = _build_registry()


def list_generation_providers() -> list[dict[str, Any]]:
    return [provider.health_check() for provider in _REGISTRY.values()]


def list_generation_engines() -> list[dict[str, Any]]:
    return list_generation_providers()


def get_generation_provider(name: str) -> GenerationProvider:
    normalized = (name or "").strip().lower()
    if normalized not in _REGISTRY:
        raise KeyError(f"generation provider not found: {name}")
    return _REGISTRY[normalized]


def get_generation_engine(name: str) -> GenerationProvider:
    return get_generation_provider(name)


def list_engines_by_capability(capability: str) -> list[dict[str, Any]]:
    normalized = (capability or "").strip().lower()
    return [
        provider.health_check()
        for provider in _REGISTRY.values()
        if normalized in [str(item).lower() for item in getattr(provider, "capabilities", [])]
    ]


def get_default_engine(capability: str) -> GenerationProvider:
    engines = list_engines_by_capability(capability)
    if not engines:
        raise KeyError(f"generation engine not found for capability: {capability}")
    return get_generation_provider(str(engines[0]["engine_id"]))


def health_check_all() -> dict[str, Any]:
    items = list_generation_engines()
    return {"items": items, "available_count": sum(1 for item in items if item.get("available"))}


def provider_available(name: str) -> bool:
    return bool(get_generation_provider(name).health_check().get("available"))


def provider_health(name: str) -> dict[str, Any]:
    return get_generation_provider(name).health_check()
