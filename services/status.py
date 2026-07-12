from __future__ import annotations

from datetime import datetime, timezone
import time

from config.settings import get_git_commit, get_settings
from database import database_status
from services.atos_client import AtosAuthError, AtosClient, AtosClientError, AtosUnavailableError


_ATOS_STATUS_CACHE = {"checked_at": 0.0, "value": "Not configured"}


def atos_connection_status() -> str:
    settings = get_settings()
    if not settings.atos_base_url:
        return "Not configured"
    now = time.monotonic()
    if now - float(_ATOS_STATUS_CACHE["checked_at"]) < 10:
        return str(_ATOS_STATUS_CACHE["value"])
    try:
        AtosClient().health_check()
        value = "Connected"
    except AtosAuthError:
        value = "Authentication failed"
    except AtosUnavailableError:
        value = "Unavailable"
    except AtosClientError:
        value = "Unavailable"
    _ATOS_STATUS_CACHE["checked_at"] = now
    _ATOS_STATUS_CACHE["value"] = value
    return value


def build_health_payload() -> dict:
    settings = get_settings()
    return {
        "service": "atos-studio",
        "status": "ok",
        "version": settings.studio_version,
    }


def build_status_cards() -> list[dict]:
    settings = get_settings()
    db_status = database_status()
    atos_status = atos_connection_status()
    return [
        {"label": "Studio服务状态", "value": "Running", "class_name": "status-ok"},
        {"label": "当前版本", "value": settings.studio_version, "class_name": ""},
        {"label": "ATOS连接状态", "value": atos_status, "class_name": "status-ok" if atos_status == "Connected" else "status-warn"},
        {"label": "数据库连接状态", "value": db_status, "class_name": "status-ok" if db_status == "Connected" else "status-warn"},
        {"label": "GPU Worker状态占位", "value": settings.gpu_worker_status, "class_name": "status-warn"},
        {"label": "ComfyUI状态占位", "value": settings.comfyui_status, "class_name": "status-warn"},
        {"label": "当前环境", "value": settings.studio_env, "class_name": ""},
        {"label": "构建时间", "value": datetime.now(timezone.utc).isoformat(timespec="seconds"), "class_name": ""},
        {"label": "Git commit", "value": get_git_commit(), "class_name": ""},
    ]
