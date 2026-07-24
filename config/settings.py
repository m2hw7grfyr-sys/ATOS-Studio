from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    atos_base_url: str = "http://127.0.0.1:8000"
    atos_studio_api_token: str = ""
    atos_request_timeout_seconds: float = 10
    studio_push_auth_enabled: bool = True
    studio_push_api_token: str = ""
    atos_database_url: str = ""
    studio_database_url: str = Field(default="sqlite:///./storage/atos_studio.db")
    studio_storage_root: str = Field(default=str(ROOT_DIR / "storage"))
    studio_port: int = 8502
    comfyui_base_url: str = ""
    comfyui_enabled: bool = True
    comfyui_url: str = ""
    comfyui_timeout_seconds: float = 120
    studio_model_root: str = Field(default=str(ROOT_DIR / "storage" / "models"))
    studio_workflow_root: str = Field(default=str(ROOT_DIR / "storage" / "workflows"))
    studio_output_root: str = Field(default=str(ROOT_DIR / "storage" / "outputs"))
    studio_temp_root: str = Field(default=str(ROOT_DIR / "storage" / "tmp"))
    studio_preflight_cache_seconds: int = 30
    studio_min_free_disk_gb: float = 1.0
    studio_allow_preset_fallback: bool = False
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    gpu_worker_url: str = ""
    backup_provider: str = "none"
    backup_target: str = ""
    log_level: str = "INFO"
    studio_env: str = "development"
    studio_version: str = "0.1.0"
    ai_provider: str = "local"
    ai_default_model: str = "qwen3"
    ai_timeout_seconds: float = 120
    ai_max_tokens: int = 1200
    ai_temperature: float = 0.3
    ai_output_format: str = "json"
    local_llm_type: str = "ollama"
    local_llm_url: str = "http://127.0.0.1:11434"
    local_llm_model: str = "qwen3"
    local_llm_timeout_seconds: float = 120
    openai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = ""
    openai_timeout_seconds: float = 120

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def comfyui_status(self) -> str:
        return "Configured" if self.comfyui_effective_url else "Not configured"

    @property
    def comfyui_effective_url(self) -> str:
        return (self.comfyui_url or self.comfyui_base_url or "").rstrip("/")

    @property
    def gpu_worker_status(self) -> str:
        return "Configured" if self.gpu_worker_url else "Not configured"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_git_commit() -> str:
    env_commit = os.getenv("GIT_COMMIT", "").strip()
    if env_commit:
        return env_commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def database_connection_status(database_url: Optional[str]) -> str:
    if not database_url:
        return "Not configured"
    if database_url.startswith("sqlite:///"):
        path = Path(database_url.removeprefix("sqlite:///"))
        return "Configured" if path.parent.exists() else "Storage path missing"
    return "Configured"
