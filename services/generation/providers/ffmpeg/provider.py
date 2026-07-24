from __future__ import annotations

import shutil
import subprocess
from typing import Any

from config.settings import get_settings
from services.generation.providers.base import GenerationProvider


class FFmpegProvider(GenerationProvider):
    provider_name = "ffmpeg"
    provider_type = "local_binary"
    display_name = "FFmpeg"
    capabilities = ["composition"]

    def __init__(self) -> None:
        settings = get_settings()
        self.ffmpeg_binary = settings.ffmpeg_binary
        self.ffprobe_binary = settings.ffprobe_binary
        self.enabled = True

    def _binary_status(self, binary: str) -> dict[str, Any]:
        path = shutil.which(binary)
        if not path:
            return {"binary": binary, "available": False, "path": "", "version": ""}
        try:
            result = subprocess.run([path, "-version"], check=False, capture_output=True, text=True, timeout=5)
            first_line = (result.stdout or result.stderr or "").splitlines()[0] if (result.stdout or result.stderr) else ""
        except Exception as exc:
            return {"binary": binary, "available": False, "path": path, "version": "", "error": str(exc)}
        return {"binary": binary, "available": result.returncode == 0, "path": path, "version": first_line}

    def health_check(self) -> dict[str, Any]:
        ffmpeg = self._binary_status(self.ffmpeg_binary)
        ffprobe = self._binary_status(self.ffprobe_binary)
        available = bool(ffmpeg.get("available") and ffprobe.get("available"))
        return {
            "provider": self.provider_name,
            "engine_id": self.provider_name,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "enabled": self.enabled,
            "provider_type": self.provider_type,
            "available": available,
            "status": "available" if available else "unavailable",
            "message": "FFmpeg and FFprobe are available." if available else "FFmpeg or FFprobe is not available.",
            "details": {"ffmpeg": ffmpeg, "ffprobe": ffprobe},
        }
