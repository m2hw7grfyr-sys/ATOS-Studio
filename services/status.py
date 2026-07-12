from __future__ import annotations

from datetime import datetime, timezone

from config.settings import database_connection_status, get_git_commit, get_settings


def build_health_payload() -> dict:
    settings = get_settings()
    return {
        "service": "atos-studio",
        "status": "ok",
        "version": settings.studio_version,
    }


def build_status_cards() -> list[dict]:
    settings = get_settings()
    db_status = database_connection_status(settings.studio_database_url)
    atos_status = "Configured" if settings.atos_base_url else "Not configured"
    return [
        {"label": "Studio服务状态", "value": "Running", "class_name": "status-ok"},
        {"label": "当前版本", "value": settings.studio_version, "class_name": ""},
        {"label": "ATOS连接状态", "value": atos_status, "class_name": "status-ok" if atos_status == "Configured" else "status-warn"},
        {"label": "数据库连接状态", "value": db_status, "class_name": "status-ok" if db_status == "Configured" else "status-warn"},
        {"label": "GPU Worker状态占位", "value": settings.gpu_worker_status, "class_name": "status-warn"},
        {"label": "ComfyUI状态占位", "value": settings.comfyui_status, "class_name": "status-warn"},
        {"label": "当前环境", "value": settings.studio_env, "class_name": ""},
        {"label": "构建时间", "value": datetime.now(timezone.utc).isoformat(timespec="seconds"), "class_name": ""},
        {"label": "Git commit", "value": get_git_commit(), "class_name": ""},
    ]

