from __future__ import annotations

import json
from html import escape
from urllib.parse import quote, parse_qs

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from config.settings import get_settings
from database import get_db
from models.content_item import StudioContentItem
from models.schemas import (
    ContentItemListResponse,
    ImportContentItemRequest,
    ImportContentItemResponse,
    StudioContentItemRead,
    UpdateContentStatusRequest,
    VALID_CONTENT_STATUSES,
)
from repositories.content_items import ContentItemRepository, serialize_item
from services.atos_client import AtosAuthError, AtosClient, AtosClientError, AtosNotFoundError, AtosUnavailableError
from services.status import build_health_payload, build_status_cards


settings = get_settings()
app = FastAPI(
    title="ATOS Studio",
    version=settings.studio_version,
    description="ATOS Studio 1.0 minimal service shell",
)


NAV_ITEMS = [
    ("home", "/", "首页"),
    ("inspiration", "/inspiration", "灵感中心"),
    ("content-pool", "/content-pool", "内容池"),
    ("video-projects", "/video-projects", "视频项目"),
    ("generation-queue", "/generation-queue", "生成队列"),
    ("assets", "/assets", "素材库"),
    ("renders", "/renders", "成片库"),
    ("settings", "/settings", "Studio设置"),
]

PLACEHOLDER_PAGES = {
    "inspiration": "灵感中心",
    "video-projects": "视频项目",
    "generation-queue": "生成队列",
    "assets": "素材库",
    "renders": "成片库",
    "settings": "Studio设置",
}


def render_shell(active_key: str, title: str, body: str) -> HTMLResponse:
    nav = "\n".join(
        f'<a class="nav-item {"active" if key == active_key else ""}" href="{href}">{label}</a>'
        for key, href, label in NAV_ITEMS
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} · ATOS Studio</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7f8fb;
        --panel: #ffffff;
        --ink: #17202a;
        --muted: #667085;
        --line: #d9dee8;
        --accent: #1769aa;
        --good: #16794c;
        --warn: #9a6700;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--ink);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .layout {{ display: grid; grid-template-columns: 232px minmax(0, 1fr); min-height: 100vh; }}
      aside {{ border-right: 1px solid var(--line); background: #111827; color: white; padding: 22px 16px; }}
      .brand {{ font-size: 20px; font-weight: 750; margin-bottom: 24px; }}
      .nav-item {{
        display: block;
        color: #cbd5e1;
        text-decoration: none;
        padding: 11px 12px;
        border-radius: 6px;
        margin-bottom: 4px;
        font-size: 14px;
      }}
      .nav-item.active, .nav-item:hover {{ background: #243044; color: #ffffff; }}
      main {{ padding: 30px; }}
      h1 {{ margin: 0 0 10px; font-size: 30px; letter-spacing: 0; }}
      .subtitle {{ color: var(--muted); margin-bottom: 24px; }}
      .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
      .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; min-height: 98px; }}
      .label {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
      .value {{ font-size: 19px; font-weight: 720; overflow-wrap: anywhere; }}
      .status-ok {{ color: var(--good); }}
      .status-warn {{ color: var(--warn); }}
      .placeholder {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 22px; max-width: 720px; }}
      .toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin: 18px 0; }}
      .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
      .field {{ min-height: 38px; border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; min-width: 170px; }}
      .button {{ min-height: 38px; border: 0; border-radius: 6px; background: var(--accent); color: #fff; padding: 8px 12px; cursor: pointer; }}
      .button.secondary {{ background: #475569; }}
      .button.danger {{ background: #b42318; }}
      table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
      th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 14px; }}
      th {{ color: var(--muted); font-weight: 650; background: #f1f4f8; }}
      .actions {{ display: flex; flex-wrap: wrap; gap: 6px; }}
      .notice {{ border-radius: 6px; padding: 10px 12px; margin: 12px 0; background: #eef7f1; color: var(--good); }}
      .notice.warn {{ background: #fff7e6; color: var(--warn); }}
      .detail-grid {{ display: grid; grid-template-columns: 160px minmax(0, 1fr); gap: 10px 14px; }}
      pre {{ overflow: auto; background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 8px; }}
      code {{ background: #eef2f7; padding: 2px 5px; border-radius: 4px; }}
      @media (max-width: 760px) {{
        .layout {{ grid-template-columns: 1fr; }}
        aside {{ border-right: 0; }}
        main {{ padding: 20px; }}
      }}
    </style>
  </head>
  <body>
    <div class="layout">
      <aside>
        <div class="brand">ATOS Studio</div>
        <nav>{nav}</nav>
      </aside>
      <main>{body}</main>
    </div>
  </body>
</html>"""
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    cards = build_status_cards()
    card_html = "\n".join(
        f'<section class="card"><div class="label">{card["label"]}</div>'
        f'<div class="value {card["class_name"]}">{card["value"]}</div></section>'
        for card in cards
    )
    body = f"""
      <h1>ATOS Studio</h1>
      <p class="subtitle">Studio服务状态和集成占位信息</p>
      <div class="grid">{card_html}</div>
    """
    return render_shell("home", "首页", body)


@app.get("/health")
def health() -> dict:
    return build_health_payload()


def atos_connection_label() -> str:
    settings = get_settings()
    if not settings.atos_base_url:
        return "Not configured"
    try:
        AtosClient().health_check()
        return "Connected"
    except AtosAuthError:
        return "Authentication failed"
    except AtosUnavailableError:
        return "Unavailable"
    except AtosClientError:
        return "Unavailable"


def message_html(message: str = "", level: str = "ok") -> str:
    if not message:
        return ""
    class_name = "notice warn" if level == "warn" else "notice"
    return f'<div class="{class_name}">{escape(message)}</div>'


def item_actions(item_id: str) -> str:
    buttons = []
    for next_status, label, class_name in [
        ("approved", "批准", ""),
        ("rejected", "拒绝", "danger"),
        ("archived", "归档", "secondary"),
    ]:
        buttons.append(
            f'<form method="post" action="/content-pool/{escape(item_id)}/status">'
            f'<input type="hidden" name="status" value="{next_status}">'
            f'<button class="button {class_name}" type="submit">{label}</button></form>'
        )
    return '<div class="actions">' + f'<a class="button secondary" href="/content-pool/{escape(item_id)}">查看</a>' + "".join(buttons) + "</div>"


def content_pool_table(items: list[StudioContentItemRead]) -> str:
    if not items:
        return '<div class="placeholder">内容池暂无数据</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(item.title)}</td>"
            f"<td>{escape(item.source_platform)}</td>"
            f"<td>{escape(item.author or '')}</td>"
            f"<td>{'' if item.source_score is None else item.source_score}</td>"
            f"<td>{'' if item.comment_count is None else item.comment_count}</td>"
            f"<td>{escape(item.risk_level or '')}</td>"
            f"<td>{escape(item.status)}</td>"
            f"<td>{escape(item.imported_at.isoformat())}</td>"
            f"<td>{item_actions(item.id)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>标题</th><th>平台</th><th>作者</th><th>来源评分</th><th>评论数</th>"
        "<th>风险等级</th><th>状态</th><th>导入时间</th><th>操作</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


@app.get("/content-pool", response_class=HTMLResponse)
def content_pool_page(
    msg: str = "",
    level: str = "ok",
    status_filter: str = Query(default="", alias="status"),
    platform: str = "",
    search: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = ContentItemRepository(db)
    rows, total = repo.list(status_filter or None, platform or None, search or None, limit=50, offset=0)
    items = [serialize_item(row) for row in rows]
    body = f"""
      <h1>内容池</h1>
      <p class="subtitle">ATOS连接状态：<strong>{escape(atos_connection_label())}</strong></p>
      {message_html(msg, level)}
      <section class="panel">
        <h2>从ATOS导入</h2>
        <form method="post" action="/content-pool/import" class="toolbar">
          <label>平台<br><input class="field" name="source_platform" value="reddit" required></label>
          <label>ATOS帖子ID或source_post_id<br><input class="field" name="source_post_id" required></label>
          <button class="button" type="submit">从ATOS导入</button>
        </form>
      </section>
      <section class="panel">
        <h2>内容池列表</h2>
        <form method="get" action="/content-pool" class="toolbar">
          <label>状态<br><input class="field" name="status" value="{escape(status_filter)}"></label>
          <label>平台<br><input class="field" name="platform" value="{escape(platform)}"></label>
          <label>搜索<br><input class="field" name="search" value="{escape(search)}"></label>
          <button class="button secondary" type="submit">筛选</button>
        </form>
        <p class="subtitle">共 {total} 条</p>
        {content_pool_table(items)}
      </section>
    """
    return render_shell("content-pool", "内容池", body)


@app.get("/content-pool/{item_id}", response_class=HTMLResponse)
def content_pool_detail(item_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    row = db.get(StudioContentItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="content item not found")
    item = serialize_item(row)
    snapshot = json.dumps(item.source_snapshot, ensure_ascii=False, indent=2)
    tags = ", ".join(str(tag) for tag in item.tags)
    body = f"""
      <h1>{escape(item.title)}</h1>
      <p class="subtitle"><a href="/content-pool">返回内容池</a></p>
      <section class="panel detail-grid">
        <div>标题</div><div>{escape(item.title)}</div>
        <div>正文</div><div>{escape(item.body)}</div>
        <div>来源链接</div><div><a href="{escape(item.source_url or '#')}">{escape(item.source_url or '')}</a></div>
        <div>平台</div><div>{escape(item.source_platform)}</div>
        <div>作者</div><div>{escape(item.author or '')}</div>
        <div>发布时间</div><div>{escape(item.published_at.isoformat() if item.published_at else '')}</div>
        <div>ATOS ID</div><div>{escape(item.atos_post_id or '')}</div>
        <div>平台post ID</div><div>{escape(item.source_post_id or '')}</div>
        <div>来源评分</div><div>{'' if item.source_score is None else item.source_score}</div>
        <div>评论数</div><div>{'' if item.comment_count is None else item.comment_count}</div>
        <div>风险等级</div><div>{escape(item.risk_level or '')}</div>
        <div>标签</div><div>{escape(tags)}</div>
        <div>状态</div><div>{escape(item.status)}</div>
        <div>导入时间</div><div>{escape(item.imported_at.isoformat())}</div>
      </section>
      <details class="panel"><summary>原始source snapshot</summary><pre>{escape(snapshot)}</pre></details>
    """
    return render_shell("content-pool", "内容详情", body)


async def parse_urlencoded(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


@app.post("/content-pool/import")
async def content_pool_import_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    source_platform = form.get("source_platform", "").strip()
    source_post_id = form.get("source_post_id", "").strip()
    try:
        result, created = import_content_item_from_atos(db, source_platform, source_post_id)
        db.commit()
        msg = "导入成功" if created else "已存在，未重复创建"
        return RedirectResponse(f"/content-pool?msg={quote(msg)}", status_code=303)
    except AtosNotFoundError:
        msg = "ATOS中未找到该帖子"
    except AtosAuthError:
        msg = "ATOS鉴权失败"
    except AtosUnavailableError:
        msg = "ATOS服务不可达"
    except Exception as exc:
        msg = str(exc)
    db.rollback()
    return RedirectResponse(f"/content-pool?level=warn&msg={quote(msg)}", status_code=303)


@app.post("/content-pool/{item_id}/status")
async def content_pool_status_form(item_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    update_item_status(db, item_id, form.get("status", ""))
    db.commit()
    return RedirectResponse("/content-pool", status_code=303)


def import_content_item_from_atos(db: Session, source_platform: str, source_post_id: str):
    if not source_platform or not source_post_id:
        raise HTTPException(status_code=422, detail="source_platform and source_post_id are required")
    atos_item = AtosClient().get_content_item(source_post_id)
    if atos_item.source_platform.lower() != source_platform.lower():
        raise HTTPException(status_code=422, detail="source platform does not match ATOS item")
    repo = ContentItemRepository(db)
    return repo.import_from_atos(atos_item)


def update_item_status(db: Session, item_id: str, next_status: str):
    if next_status not in VALID_CONTENT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid content item status")
    row = db.get(StudioContentItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="content item not found")
    row.status = next_status
    db.flush()
    return row


@app.post("/api/content-items/import")
def import_content_item_api(
    payload: ImportContentItemRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    row, created = import_content_item_from_atos(db, payload.source_platform, payload.source_post_id)
    db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    result = ImportContentItemResponse(
        created=created,
        duplicate=not created,
        item=serialize_item(row),
    )
    return result.model_dump(mode="json")


@app.get("/api/content-items")
def list_content_items_api(
    status_filter: str = Query(default="", alias="status"),
    platform: str = "",
    search: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    if status_filter and status_filter not in VALID_CONTENT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid content item status")
    rows, total = ContentItemRepository(db).list(
        status_filter or None,
        platform or None,
        search or None,
        limit,
        offset,
    )
    payload = ContentItemListResponse(
        items=[serialize_item(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
    return payload.model_dump(mode="json")


@app.get("/api/content-items/{item_id}")
def get_content_item_api(item_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(StudioContentItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="content item not found")
    return serialize_item(row).model_dump(mode="json")


@app.patch("/api/content-items/{item_id}/status")
def update_content_item_status_api(
    item_id: str,
    payload: UpdateContentStatusRequest,
    db: Session = Depends(get_db),
) -> dict:
    row = update_item_status(db, item_id, payload.status)
    db.commit()
    return serialize_item(row).model_dump(mode="json")


def placeholder_page(page_key: str) -> HTMLResponse:
    label = PLACEHOLDER_PAGES[page_key]
    body = f"""
      <h1>{label}</h1>
      <div class="placeholder">该模块将在后续Sprint实现</div>
    """
    return render_shell(page_key, label, body)


@app.get("/inspiration", response_class=HTMLResponse)
def inspiration() -> HTMLResponse:
    return placeholder_page("inspiration")


@app.get("/video-projects", response_class=HTMLResponse)
def video_projects() -> HTMLResponse:
    return placeholder_page("video-projects")


@app.get("/generation-queue", response_class=HTMLResponse)
def generation_queue() -> HTMLResponse:
    return placeholder_page("generation-queue")


@app.get("/assets", response_class=HTMLResponse)
def assets() -> HTMLResponse:
    return placeholder_page("assets")


@app.get("/renders", response_class=HTMLResponse)
def renders() -> HTMLResponse:
    return placeholder_page("renders")


@app.get("/settings", response_class=HTMLResponse)
def studio_settings() -> HTMLResponse:
    return placeholder_page("settings")
