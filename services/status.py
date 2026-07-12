from __future__ import annotations

from datetime import datetime, timezone
import time

from config.settings import get_git_commit, get_settings
from database import SessionLocal, database_status
from models.content_item import StudioContentItem, utc_now
from sqlalchemy import func, select
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
    stats = {
        "total": "Unavailable",
        "pending": "Unavailable",
        "atos_push": "Unavailable",
        "today": "Unavailable",
    }
    try:
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        with SessionLocal() as db:
            stats = {
                "total": str(db.scalar(select(func.count()).select_from(StudioContentItem)) or 0),
                "pending": str(db.scalar(select(func.count()).where(StudioContentItem.status == "pending_review")) or 0),
                "atos_push": str(db.scalar(select(func.count()).where(StudioContentItem.source_type == "atos_manual_push")) or 0),
                "today": str(db.scalar(select(func.count()).where(StudioContentItem.imported_at >= today_start)) or 0),
            }
    except Exception:
        pass
    return [
        {"label": "Studio服务状态", "value": "Running", "class_name": "status-ok"},
        {"label": "内容池总数", "value": stats["total"], "class_name": "status-ok" if stats["total"] != "Unavailable" else "status-warn"},
        {"label": "待审核数量", "value": stats["pending"], "class_name": "status-ok" if stats["pending"] != "Unavailable" else "status-warn"},
        {"label": "ATOS手工推送", "value": stats["atos_push"], "class_name": "status-ok" if stats["atos_push"] != "Unavailable" else "status-warn"},
        {"label": "今日新增", "value": stats["today"], "class_name": "status-ok" if stats["today"] != "Unavailable" else "status-warn"},
        {"label": "当前版本", "value": settings.studio_version, "class_name": ""},
        {"label": "ATOS连接状态", "value": atos_status, "class_name": "status-ok" if atos_status == "Connected" else "status-warn"},
        {"label": "数据库连接状态", "value": db_status, "class_name": "status-ok" if db_status == "Connected" else "status-warn"},
        {"label": "GPU Worker状态占位", "value": settings.gpu_worker_status, "class_name": "status-warn"},
        {"label": "ComfyUI状态占位", "value": settings.comfyui_status, "class_name": "status-warn"},
        {"label": "当前环境", "value": settings.studio_env, "class_name": ""},
        {"label": "构建时间", "value": datetime.now(timezone.utc).isoformat(timespec="seconds"), "class_name": ""},
        {"label": "Git commit", "value": get_git_commit(), "class_name": ""},
    ]
