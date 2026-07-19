from __future__ import annotations

import json
import secrets
from html import escape
from urllib.parse import quote, parse_qs
from typing import Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import get_settings
from database import get_db
from models.content_item import StudioContentItem
from models.ai import StudioEditorialBrief
from models.topic_package import StudioTopicPackage
from models.schemas import (
    ContentItemStatusBatchRequest,
    ContentItemListResponse,
    ImportContentItemRequest,
    ImportContentItemResponse,
    StudioContentItemRead,
    StudioContentPushRequest,
    StudioContentPushResponse,
    StudioSourceStatusBatchRequest,
    StudioSourceStatusResponse,
    TopicPackageFromContentItemsRequest,
    TopicPackageItemBatchAddRequest,
    TopicPackageItemsOrderRequest,
    TopicPackageMergeRequest,
    TopicPackageCreate,
    TopicPackagePrimaryItemRequest,
    TopicPackageStatusUpdate,
    TopicPackageUpdate,
    UpdateContentStatusRequest,
    VALID_CONTENT_STATUSES,
    VALID_TOPIC_PACKAGE_STATUSES,
)
from repositories.content_items import ContentItemRepository, serialize_item
from services.atos_client import AtosAuthError, AtosClient, AtosClientError, AtosNotFoundError, AtosUnavailableError
from services.status import build_health_payload, build_status_cards
from services.ai_service import (
    ai_health_payload,
    create_ai_job,
    create_default_topic_ai_jobs,
    create_prompt_template,
    list_prompt_templates,
    run_ai_job,
    serialize_ai_job,
    serialize_prompt_template,
    topic_ai_analyses,
    topic_ai_jobs,
)
from services.gpt_prompt_builder import (
    build_editorial_prompt,
    editorial_context,
    save_editorial_output,
    serialize_editorial_brief,
    update_editorial_brief_status,
)
from services.topic_intelligence_service import TOPIC_INTELLIGENCE_JOB_TYPE
from services.topic_packages import (
    add_items_to_topic_package,
    batch_update_content_status,
    content_topic_memberships,
    create_topic_package,
    create_topic_package_from_content_items,
    find_similar_topic_packages,
    list_topic_packages,
    merge_topic_packages,
    remove_item_from_topic_package,
    reorder_topic_items,
    serialize_topic_package,
    set_primary_item,
    topic_package_audit_events,
    update_content_status_with_audit,
    update_topic_package,
    update_topic_package_status,
)


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
    ("topic-packages", "/topic-packages", "主题包"),
    ("gpt-director", "/gpt-director", "GPT编导"),
    ("video-projects", "/video-projects", "视频项目"),
    ("generation-queue", "/generation-queue", "生成队列"),
    ("assets", "/assets", "素材库"),
    ("renders", "/renders", "成片库"),
    ("settings", "/settings", "Studio设置"),
]

PLACEHOLDER_PAGES = {
    "inspiration": "灵感中心",
    "video-projects": "视频项目",
    "gpt-director": "GPT编导",
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
    return (
        '<div class="actions">'
        + f'<a class="button secondary" href="/content-pool/{escape(item_id)}">查看</a>'
        + f'<a class="button secondary" href="/topic-packages/new?content_item_id={escape(item_id)}">创建主题包</a>'
        + "".join(buttons)
        + "</div>"
    )


def status_counts(db: Session) -> dict[str, int]:
    counts = {status: 0 for status in VALID_CONTENT_STATUSES}
    rows = db.query(StudioContentItem.status, func.count(StudioContentItem.id)).group_by(StudioContentItem.status).all()
    for status_name, count in rows:
        counts[str(status_name)] = int(count)
    counts["all"] = sum(counts.values())
    return counts


def require_push_token(authorization: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.studio_push_auth_enabled:
        if settings.studio_env.lower() == "development":
            return
        raise HTTPException(status_code=403, detail="studio push auth cannot be disabled outside development")
    expected = settings.studio_push_api_token
    if not expected:
        raise HTTPException(status_code=401, detail="studio push api token is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing studio push bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid studio push bearer token")


def content_pool_table(items: list[StudioContentItemRead]) -> str:
    if not items:
        return '<div class="placeholder">内容池暂无数据</div>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f'<td><input form="content-batch-form" type="checkbox" name="content_item_ids" value="{escape(item.id)}"></td>'
            f"<td>{escape(item.title)}</td>"
            f"<td>{escape(item.source_platform)}</td>"
            f"<td>{escape(item.author or '')}</td>"
            f"<td>{'' if item.source_score is None else item.source_score}</td>"
            f"<td>{'' if item.comment_count is None else item.comment_count}</td>"
            f"<td>{escape(item.risk_level or '')}</td>"
            f"<td>{escape(item.source_type)}</td>"
            f"<td>{escape(item.requested_content_type or '')}</td>"
            f"<td>{escape(', '.join(item.target_platforms))}</td>"
            f"<td>{escape(str(item.push_count))}</td>"
            f"<td>{escape(item.last_pushed_at.isoformat() if item.last_pushed_at else '')}</td>"
            f"<td>{escape(item.status)}</td>"
            f"<td>{escape(item.imported_at.isoformat())}</td>"
            f"<td>{item_actions(item.id)}</td>"
            "</tr>"
        )
    return (
        '<form id="content-batch-form" method="post" action="/content-pool/status-batch-form"></form>'
        '<div class="toolbar">'
        '<label>批量状态<br><select form="content-batch-form" class="field" name="status">'
        '<option value="approved">批准</option><option value="rejected">拒绝</option>'
        '<option value="archived">归档</option><option value="pending_review">恢复待审核</option>'
        '</select></label>'
        '<label>审核备注<br><input form="content-batch-form" class="field" name="review_note" placeholder="可选"></label>'
        '<button form="content-batch-form" class="button" type="submit">执行批量审核</button>'
        '<button form="content-batch-form" class="button secondary" type="submit" formaction="/topic-packages/from-content-items-form">用所选内容创建主题包</button>'
        "</div>"
        "<table><thead><tr>"
        "<th>选择</th><th>标题</th><th>平台</th><th>作者</th><th>来源评分</th><th>评论数</th>"
        "<th>风险等级</th><th>来源类型</th><th>目标内容</th><th>目标平台</th><th>推送次数</th><th>最后推送</th>"
        "<th>状态</th><th>导入时间</th><th>操作</th>"
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
    source_type: str = "",
    risk_level: str = "",
    target_content_type: str = "",
    search: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = ContentItemRepository(db)
    rows, total = repo.list(
        status_filter or None,
        platform or None,
        search or None,
        limit=50,
        offset=0,
        source_type=source_type or None,
        risk_level=risk_level or None,
        target_content_type=target_content_type or None,
    )
    items = [serialize_item(row) for row in rows]
    counts = status_counts(db)
    stats_html = "".join(
        f'<section class="card"><div class="label">{label}</div><div class="value">{value}</div></section>'
        for label, value in [
            ("全部", counts["all"]),
            ("待审核", counts["pending_review"]),
            ("已批准", counts["approved"]),
            ("已拒绝", counts["rejected"]),
            ("已归档", counts["archived"]),
        ]
    )
    body = f"""
      <h1>内容池</h1>
      <p class="subtitle">ATOS连接状态：<strong>{escape(atos_connection_label())}</strong></p>
      {message_html(msg, level)}
      <div class="grid">{stats_html}</div>
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
          <label>来源类型<br><input class="field" name="source_type" value="{escape(source_type)}" placeholder="atos_manual_push"></label>
          <label>风险等级<br><input class="field" name="risk_level" value="{escape(risk_level)}" placeholder="low / medium / high"></label>
          <label>目标内容<br><input class="field" name="target_content_type" value="{escape(target_content_type)}" placeholder="video"></label>
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
    memberships = content_topic_memberships(db, item.id)
    memberships_html = (
        "<table><thead><tr><th>主题包</th><th>状态</th><th>主要来源</th><th>加入时间</th><th>操作</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(member["title"])}</td>'
            f'<td>{escape(member["status"])}</td>'
            f'<td>{"是" if member["is_primary"] else "否"}</td>'
            f'<td>{escape(member["added_at"] or "")}</td>'
            f'<td><a class="button secondary" href="/topic-packages/{escape(member["topic_package_id"])}">查看主题包</a></td>'
            "</tr>"
            for member in memberships
        )
        + "</tbody></table>"
        if memberships
        else '<div class="placeholder">当前内容尚未加入任何主题包</div>'
    )
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
        <div>来源类型</div><div>{escape(item.source_type)}</div>
        <div>目标内容类型</div><div>{escape(item.requested_content_type or '')}</div>
        <div>目标平台</div><div>{escape(', '.join(item.target_platforms))}</div>
        <div>操作备注</div><div>{escape(item.operator_note or '')}</div>
        <div>推送次数</div><div>{escape(str(item.push_count))}</div>
        <div>最后推送时间</div><div>{escape(item.last_pushed_at.isoformat() if item.last_pushed_at else '')}</div>
        <div>状态</div><div>{escape(item.status)}</div>
        <div>导入时间</div><div>{escape(item.imported_at.isoformat())}</div>
      </section>
      <section class="panel">
        <h2>所属主题包</h2>
        {memberships_html}
      </section>
      <details class="panel"><summary>原始source snapshot</summary><pre>{escape(snapshot)}</pre></details>
    """
    return render_shell("content-pool", "内容详情", body)


async def parse_urlencoded(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


async def parse_urlencoded_multi(request: Request) -> dict[str, list[str]]:
    body = (await request.body()).decode("utf-8")
    return parse_qs(body, keep_blank_values=True)


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
    update_item_status(db, item_id, form.get("status", ""), form.get("review_note", ""))
    db.commit()
    return RedirectResponse("/content-pool", status_code=303)


@app.post("/content-pool/status-batch-form")
async def content_pool_status_batch_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded_multi(request)
    ids = form.get("content_item_ids", [])
    status_value = (form.get("status", [""])[-1] or "").strip()
    review_note = (form.get("review_note", [""])[-1] or "").strip()
    if not ids:
        return RedirectResponse("/content-pool?level=warn&msg=请先选择内容项", status_code=303)
    try:
        result = batch_update_content_status(db, ids, status_value, review_note)
        db.commit()
        msg = f"批量审核完成：成功 {result['updated']}，失败 {result['failed']}"
        return RedirectResponse(f"/content-pool?msg={quote(msg)}", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/content-pool?level=warn&msg={quote(str(exc))}", status_code=303)


def import_content_item_from_atos(db: Session, source_platform: str, source_post_id: str):
    if not source_platform or not source_post_id:
        raise HTTPException(status_code=422, detail="source_platform and source_post_id are required")
    atos_item = AtosClient().get_content_item(source_post_id)
    if atos_item.source_platform.lower() != source_platform.lower():
        raise HTTPException(status_code=422, detail="source platform does not match ATOS item")
    repo = ContentItemRepository(db)
    return repo.import_from_atos(atos_item)


def update_item_status(db: Session, item_id: str, next_status: str, review_note: str = ""):
    return update_content_status_with_audit(db, item_id, next_status, review_note)


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


@app.post("/api/content-items/push")
def push_content_item_api(
    payload: StudioContentPushRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(require_push_token),
) -> dict:
    try:
        row, created = ContentItemRepository(db).push_from_atos(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return StudioContentPushResponse(
        created=created,
        duplicate=not created,
        studio_item_id=row.id,
        status=row.status,
        source_type=row.source_type,
    ).model_dump(mode="json")


def source_status_payload(row: StudioContentItem | None) -> StudioSourceStatusResponse:
    if not row:
        return StudioSourceStatusResponse(exists=False)
    return StudioSourceStatusResponse(
        exists=True,
        studio_item_id=row.id,
        status=row.status,
        source_type=row.source_type,
        imported_at=row.imported_at,
        last_pushed_at=row.last_pushed_at,
    )


@app.get("/api/content-items/source-status")
def source_status_api(
    source_platform: str = Query(default=""),
    source_post_id: str = "",
    atos_post_id: str = "",
    db: Session = Depends(get_db),
    _: None = Depends(require_push_token),
) -> dict:
    if not source_platform or (not source_post_id and not atos_post_id):
        raise HTTPException(status_code=422, detail="source_platform and source_post_id or atos_post_id are required")
    row = ContentItemRepository(db).find_by_source(source_platform, source_post_id or None, atos_post_id or None)
    return source_status_payload(row).model_dump(mode="json")


@app.post("/api/content-items/source-status/batch")
def source_status_batch_api(
    payload: StudioSourceStatusBatchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_push_token),
) -> dict:
    repo = ContentItemRepository(db)
    results = []
    for item in payload.items:
        row = repo.find_by_source(item.source_platform, item.source_post_id, item.atos_post_id)
        status_payload = source_status_payload(row).model_dump(mode="json")
        status_payload.update(
            {
                "source_platform": item.source_platform,
                "source_post_id": item.source_post_id,
                "atos_post_id": item.atos_post_id,
            }
        )
        results.append(status_payload)
    return {"items": results}


@app.get("/api/content-items")
def list_content_items_api(
    status_filter: str = Query(default="", alias="status"),
    platform: str = "",
    source_type: str = "",
    risk_level: str = "",
    target_content_type: str = "",
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
        source_type=source_type or None,
        risk_level=risk_level or None,
        target_content_type=target_content_type or None,
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
    row = update_item_status(db, item_id, payload.status, payload.review_note)
    db.commit()
    return serialize_item(row).model_dump(mode="json")


@app.post("/api/content-items/status-batch")
def update_content_item_status_batch_api(
    payload: ContentItemStatusBatchRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = batch_update_content_status(db, payload.content_item_ids, payload.status, payload.review_note)
    db.commit()
    return result


@app.post("/api/topic-packages")
def create_topic_package_api(payload: TopicPackageCreate, db: Session = Depends(get_db)) -> dict:
    package = create_topic_package(db, payload)
    db.commit()
    return serialize_topic_package(db, package, include_items=True)


@app.get("/api/topic-packages")
def list_topic_packages_api(
    status_filter: str = Query(default="", alias="status"),
    priority: str = "",
    risk_level: str = "",
    target_platform: str = "",
    search: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    return list_topic_packages(
        db,
        status_filter or None,
        priority or None,
        risk_level or None,
        target_platform or None,
        search or None,
        limit,
        offset,
    )


@app.get("/api/topic-packages/similar")
def similar_topic_packages_api(title: str = Query(min_length=1), db: Session = Depends(get_db)) -> dict:
    return {"items": find_similar_topic_packages(db, title)}


@app.post("/api/topic-packages/from-content-items")
def create_topic_package_from_content_items_api(
    payload: TopicPackageFromContentItemsRequest,
    db: Session = Depends(get_db),
) -> dict:
    package = create_topic_package_from_content_items(db, payload)
    db.commit()
    return serialize_topic_package(db, package, include_items=True)


@app.post("/api/topic-packages/merge")
def merge_topic_packages_api(payload: TopicPackageMergeRequest, db: Session = Depends(get_db)) -> dict:
    result = merge_topic_packages(
        db,
        payload.target_topic_package_id,
        payload.source_topic_package_ids,
        payload.archive_sources,
    )
    db.commit()
    return result


@app.get("/api/topic-packages/{topic_package_id}")
def get_topic_package_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    return serialize_topic_package(db, package, include_items=True, include_audit=True)


@app.patch("/api/topic-packages/{topic_package_id}")
def update_topic_package_api(
    topic_package_id: str,
    payload: TopicPackageUpdate,
    db: Session = Depends(get_db),
) -> dict:
    package = update_topic_package(db, topic_package_id, payload)
    db.commit()
    return serialize_topic_package(db, package, include_items=True)


@app.patch("/api/topic-packages/{topic_package_id}/status")
def update_topic_package_status_api(
    topic_package_id: str,
    payload: TopicPackageStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    package = update_topic_package_status(db, topic_package_id, payload.status)
    db.commit()
    return serialize_topic_package(db, package, include_items=True)


@app.delete("/api/topic-packages/{topic_package_id}")
def archive_topic_package_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    package = update_topic_package_status(db, topic_package_id, "archived")
    db.commit()
    return serialize_topic_package(db, package)


@app.post("/api/topic-packages/{topic_package_id}/items")
def add_topic_package_items_api(
    topic_package_id: str,
    payload: TopicPackageItemBatchAddRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = add_items_to_topic_package(db, topic_package_id, payload.content_item_ids)
    db.commit()
    return result


@app.delete("/api/topic-packages/{topic_package_id}/items/{content_item_id}")
def remove_topic_package_item_api(topic_package_id: str, content_item_id: str, db: Session = Depends(get_db)) -> dict:
    result = remove_item_from_topic_package(db, topic_package_id, content_item_id)
    db.commit()
    return result


@app.patch("/api/topic-packages/{topic_package_id}/primary-item")
def set_primary_topic_package_item_api(
    topic_package_id: str,
    payload: TopicPackagePrimaryItemRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = set_primary_item(db, topic_package_id, payload.content_item_id)
    db.commit()
    return result


@app.patch("/api/topic-packages/{topic_package_id}/items/order")
def reorder_topic_package_items_api(
    topic_package_id: str,
    payload: TopicPackageItemsOrderRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = reorder_topic_items(db, topic_package_id, payload.ordered_content_item_ids)
    db.commit()
    return result


@app.get("/api/topic-packages/{topic_package_id}/audit")
def topic_package_audit_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    return {"items": topic_package_audit_events(db, topic_package_id)}


def topic_package_actions(package_id: str) -> str:
    return (
        '<div class="actions">'
        f'<a class="button secondary" href="/topic-packages/{escape(package_id)}">查看</a>'
        f'<form method="post" action="/topic-packages/{escape(package_id)}/status-form"><input type="hidden" name="status" value="approved"><button class="button" type="submit">批准</button></form>'
        f'<form method="post" action="/topic-packages/{escape(package_id)}/status-form" onsubmit="return confirm(\'确认拒绝该主题包？\')"><input type="hidden" name="status" value="rejected"><button class="button danger" type="submit">拒绝</button></form>'
        f'<form method="post" action="/topic-packages/{escape(package_id)}/status-form" onsubmit="return confirm(\'确认归档该主题包？\')"><input type="hidden" name="status" value="archived"><button class="button secondary" type="submit">归档</button></form>'
        "</div>"
    )


def topic_package_table(packages: list[dict]) -> str:
    if not packages:
        return '<div class="placeholder">暂无主题包</div>'
    rows = []
    for package in packages:
        rows.append(
            "<tr>"
            f"<td>{escape(package['title'])}</td>"
            f"<td>{escape(package['status'])}</td>"
            f"<td>{escape(package['priority'])}</td>"
            f"<td>{escape(str(package['source_count']))}</td>"
            f"<td>{escape(str(package['total_comment_count']))}</td>"
            f"<td>{'' if package['average_source_score'] is None else escape(str(package['average_source_score']))}</td>"
            f"<td>{'' if package['max_source_score'] is None else escape(str(package['max_source_score']))}</td>"
            f"<td>{escape(package['risk_level'])}</td>"
            f"<td>{escape(package.get('content_angle') or '')}</td>"
            f"<td>{escape(', '.join(package.get('target_platforms') or []))}</td>"
            f"<td>{escape(package.get('created_at') or '')}</td>"
            f"<td>{escape(package.get('updated_at') or '')}</td>"
            f"<td>{topic_package_actions(package['id'])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>标题</th><th>状态</th><th>优先级</th><th>来源数</th>"
        "<th>总评论数</th><th>平均评分</th><th>最高评分</th><th>风险</th><th>内容角度</th>"
        "<th>目标平台</th><th>创建时间</th><th>更新时间</th><th>操作</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


@app.get("/topic-packages", response_class=HTMLResponse)
def topic_packages_page(
    msg: str = "",
    level: str = "ok",
    status_filter: str = Query(default="", alias="status"),
    priority: str = "",
    risk_level: str = "",
    target_platform: str = "",
    search: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    payload = list_topic_packages(
        db,
        status_filter or None,
        priority or None,
        risk_level or None,
        target_platform or None,
        search or None,
        80,
        0,
    )
    body = f"""
      <h1>主题包</h1>
      <p class="subtitle">把多条相似来源整理成后续 GPT 编导和视频项目的稳定输入单位。</p>
      {message_html(msg, level)}
      <section class="panel">
        <h2>新建空主题包</h2>
        <form method="post" action="/topic-packages/create-form" class="toolbar">
          <label>主题标题<br><input class="field" name="title" required maxlength="300"></label>
          <label>内容角度<br><input class="field" name="content_angle" placeholder="解释型"></label>
          <label>优先级<br><select class="field" name="priority"><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option><option value="low">low</option></select></label>
          <label>目标内容<br><input class="field" name="target_content_type" value="video"></label>
          <label>目标平台<br><input class="field" name="target_platforms" value="tiktok,youtube_shorts"></label>
          <button class="button" type="submit">创建主题包</button>
        </form>
      </section>
      <section class="panel">
        <h2>筛选</h2>
        <form method="get" action="/topic-packages" class="toolbar">
          <label>状态<br><input class="field" name="status" value="{escape(status_filter)}"></label>
          <label>优先级<br><input class="field" name="priority" value="{escape(priority)}"></label>
          <label>风险<br><input class="field" name="risk_level" value="{escape(risk_level)}"></label>
          <label>目标平台<br><input class="field" name="target_platform" value="{escape(target_platform)}"></label>
          <label>关键词<br><input class="field" name="search" value="{escape(search)}"></label>
          <button class="button secondary" type="submit">筛选</button>
        </form>
      </section>
      <section class="panel">
        <h2>主题包列表</h2>
        <p class="subtitle">共 {payload["total"]} 个主题包</p>
        {topic_package_table(payload["items"])}
      </section>
    """
    return render_shell("topic-packages", "主题包", body)


@app.get("/topic-packages/new", response_class=HTMLResponse)
def topic_package_new_page(content_item_id: str = "", content_item_ids: str = "", db: Session = Depends(get_db)) -> HTMLResponse:
    ids = [item for item in [content_item_id, *content_item_ids.split(",")] if item]
    rows = [db.get(StudioContentItem, item_id) for item_id in dict.fromkeys(ids)]
    rows = [row for row in rows if row is not None]
    source_list = "".join(f"<li>{escape(row.title)} · {escape(row.source_platform)}</li>" for row in rows)
    hidden = "".join(f'<input type="hidden" name="content_item_ids" value="{escape(row.id)}">' for row in rows)
    default_title = rows[0].title if rows else ""
    body = f"""
      <h1>从内容创建主题包</h1>
      <p class="subtitle"><a href="/content-pool">返回内容池</a></p>
      <section class="panel">
        <h2>已选择来源</h2>
        <ul>{source_list or '<li>暂无来源</li>'}</ul>
      </section>
      <section class="panel">
        <form method="post" action="/topic-packages/from-content-items-form" class="toolbar">
          {hidden}
          <label>主题标题<br><input class="field" name="title" value="{escape(default_title)}" required maxlength="300"></label>
          <label>内容角度<br><input class="field" name="content_angle" placeholder="解释型"></label>
          <label>目标内容<br><input class="field" name="target_content_type" value="video"></label>
          <label>目标平台<br><input class="field" name="target_platforms" value="tiktok,youtube_shorts"></label>
          <label>主要来源ID<br><input class="field" name="primary_content_item_id" value="{escape(rows[0].id if rows else '')}"></label>
          <label>摘要<br><textarea class="field" name="summary"></textarea></label>
          <label>备注<br><textarea class="field" name="operator_note"></textarea></label>
          <button class="button" type="submit">创建主题包</button>
        </form>
      </section>
    """
    return render_shell("topic-packages", "创建主题包", body)


@app.post("/topic-packages/create-form")
async def topic_package_create_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    try:
        package = create_topic_package(
            db,
            TopicPackageCreate(
                title=form.get("title", ""),
                content_angle=form.get("content_angle") or None,
                priority=form.get("priority", "normal"),
                target_content_type=form.get("target_content_type") or None,
                target_platforms=[item.strip() for item in form.get("target_platforms", "").split(",") if item.strip()],
                operator_note=form.get("operator_note") or None,
            ),
        )
        db.commit()
        return RedirectResponse(f"/topic-packages/{package.id}?msg=主题包已创建", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/from-content-items-form")
async def topic_package_from_content_items_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded_multi(request)
    ids = form.get("content_item_ids", [])
    if not ids:
        return RedirectResponse("/content-pool?level=warn&msg=请先选择内容项", status_code=303)
    first = db.get(StudioContentItem, ids[0])
    title = (form.get("title", [""])[-1] or "").strip() or (first.title if first else "未命名主题包")
    try:
        package = create_topic_package_from_content_items(
            db,
            TopicPackageFromContentItemsRequest(
                title=title,
                content_item_ids=ids,
                summary=(form.get("summary", [""])[-1] or ""),
                content_angle=(form.get("content_angle", [""])[-1] or None),
                target_content_type=(form.get("target_content_type", ["video"])[-1] or "video"),
                target_platforms=[
                    item.strip()
                    for item in (form.get("target_platforms", ["tiktok"])[-1] or "").split(",")
                    if item.strip()
                ],
                operator_note=(form.get("operator_note", [""])[-1] or None),
                primary_content_item_id=(form.get("primary_content_item_id", [""])[-1] or None),
            ),
        )
        db.commit()
        return RedirectResponse(f"/topic-packages/{package.id}?msg=主题包已创建", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/content-pool?level=warn&msg={quote(str(exc))}", status_code=303)


def topic_package_items_table(package: dict) -> str:
    items = package.get("items") or []
    if not items:
        return '<div class="placeholder">该主题包暂无来源。允许保留空主题包，但建议继续添加来源。</div>'
    rows = []
    for item in items:
        content = item.get("content_item") or {}
        content_id = item["content_item_id"]
        package_id = package["id"]
        rows.append(
            "<tr>"
            f'<td>{"主来源" if item["is_primary"] else ""}</td>'
            f'<td>{escape(content.get("title") or "")}</td>'
            f'<td>{escape(content.get("source_platform") or "")}</td>'
            f'<td>{escape(content.get("author") or "")}</td>'
            f'<td>{"" if content.get("source_score") is None else escape(str(content.get("source_score")))}</td>'
            f'<td>{"" if content.get("comment_count") is None else escape(str(content.get("comment_count")))}</td>'
            f'<td>{escape(content.get("risk_level") or "")}</td>'
            f'<td>{escape(content.get("status") or "")}</td>'
            f'<td><a href="{escape(content.get("source_url") or "#")}">来源链接</a></td>'
            f'<td>{escape(item.get("added_at") or "")}</td>'
            '<td><div class="actions">'
            f'<form method="post" action="/topic-packages/{escape(package_id)}/primary-item-form"><input type="hidden" name="content_item_id" value="{escape(content_id)}"><button class="button secondary" type="submit">设为主要来源</button></form>'
            f'<form method="post" action="/topic-packages/{escape(package_id)}/move-item-form"><input type="hidden" name="content_item_id" value="{escape(content_id)}"><input type="hidden" name="direction" value="up"><button class="button secondary" type="submit">上移</button></form>'
            f'<form method="post" action="/topic-packages/{escape(package_id)}/move-item-form"><input type="hidden" name="content_item_id" value="{escape(content_id)}"><input type="hidden" name="direction" value="down"><button class="button secondary" type="submit">下移</button></form>'
            f'<a class="button secondary" href="/content-pool/{escape(content_id)}">查看内容</a>'
            f'<form method="post" action="/topic-packages/{escape(package_id)}/remove-item-form" onsubmit="return confirm(\'确认从主题包移除该来源？\')"><input type="hidden" name="content_item_id" value="{escape(content_id)}"><button class="button danger" type="submit">移除</button></form>'
            "</div></td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>主要</th><th>标题</th><th>平台</th><th>作者</th><th>评分</th>"
        "<th>评论数</th><th>风险</th><th>内容状态</th><th>链接</th><th>加入时间</th><th>操作</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def list_html(values: list, empty_text: str = "暂无") -> str:
    if not values:
        return f"<p>{escape(empty_text)}</p>"
    return "<ul>" + "".join(f"<li>{escape(str(value))}</li>" for value in values) + "</ul>"


def topic_intelligence_versions_html(analyses: list[dict]) -> str:
    topic_items = [item for item in analyses if item.get("analysis_type") == "topic_intelligence"]
    if not topic_items:
        return '<div class="placeholder">暂无主题智能分析。点击“生成主题智能分析”后执行任务。</div>'
    sections = []
    for index, item in enumerate(reversed(topic_items), start=1):
        result = item.get("result") or {}
        audience = result.get("audience") or {}
        video = result.get("video_direction") or {}
        score = result.get("opportunity_score") or {}
        pain_points = result.get("pain_points") or []
        quotes = result.get("user_quotes") or []
        opportunities = result.get("content_opportunities") or []
        pain_html = (
            "<table><thead><tr><th>问题</th><th>频率</th><th>情绪</th></tr></thead><tbody>"
            + "".join(
                "<tr>"
                f'<td>{escape(str(row.get("problem") or ""))}</td>'
                f'<td>{escape(str(row.get("frequency") or ""))}</td>'
                f'<td>{escape(str(row.get("emotion") or ""))}</td>'
                "</tr>"
                for row in pain_points
                if isinstance(row, dict)
            )
            + "</tbody></table>"
            if pain_points
            else "<p>暂无痛点</p>"
        )
        quotes_html = (
            "<table><thead><tr><th>用户原话</th><th>来源</th><th>互动</th></tr></thead><tbody>"
            + "".join(
                "<tr>"
                f'<td>{escape(str(row.get("quote") or ""))}</td>'
                f'<td>{escape(str(row.get("source") or ""))}</td>'
                f'<td>{escape(str(row.get("engagement") or 0))}</td>'
                "</tr>"
                for row in quotes
                if isinstance(row, dict)
            )
            + "</tbody></table>"
            if quotes
            else "<p>暂无用户原话</p>"
        )
        opportunities_html = (
            "<table><thead><tr><th>内容角度</th><th>理由</th><th>推荐形式</th></tr></thead><tbody>"
            + "".join(
                "<tr>"
                f'<td>{escape(str(row.get("angle") or ""))}</td>'
                f'<td>{escape(str(row.get("reason") or ""))}</td>'
                f'<td>{escape(str(row.get("recommended_format") or ""))}</td>'
                "</tr>"
                for row in opportunities
                if isinstance(row, dict)
            )
            + "</tbody></table>"
            if opportunities
            else "<p>暂无内容机会</p>"
        )
        sections.append(
            f"""
            <details class="panel" open>
              <summary><strong>Analysis Version {index}</strong> · {escape(item.get("provider") or "")} / {escape(item.get("model") or "")} · {escape(item.get("created_at") or "")}</summary>
              <h4>核心总结</h4>
              <p>{escape(str(result.get("core_summary") or ""))}</p>
              <h4>用户画像</h4>
              <p><strong>Persona：</strong>{escape(str(audience.get("persona") or ""))}</p>
              {list_html(audience.get("needs") or [], "暂无需求")}
              <h4>痛点分析</h4>
              {pain_html}
              <h4>情绪触发点</h4>
              {list_html(result.get("emotional_triggers") or [], "暂无情绪触发点")}
              <h4>争议点</h4>
              {list_html(result.get("controversies") or [], "暂无争议点")}
              <h4>用户原话</h4>
              {quotes_html}
              <h4>内容机会</h4>
              {opportunities_html}
              <h4>视频方向</h4>
              <div class="detail-grid">
                <div>Hook</div><div>{escape(str(video.get("recommended_hook") or ""))}</div>
                <div>风格</div><div>{escape(str(video.get("recommended_style") or ""))}</div>
                <div>目标平台</div><div>{escape(", ".join(str(platform) for platform in video.get("target_platforms") or []))}</div>
              </div>
              <h4>机会评分</h4>
              <div class="grid">
                <section class="card"><div class="label">Total</div><div class="value">{escape(str(score.get("total", 0)))}</div></section>
                <section class="card"><div class="label">Engagement</div><div class="value">{escape(str(score.get("engagement", 0)))}</div></section>
                <section class="card"><div class="label">Comment Quality</div><div class="value">{escape(str(score.get("comment_quality", 0)))}</div></section>
                <section class="card"><div class="label">Emotion</div><div class="value">{escape(str(score.get("emotion", 0)))}</div></section>
                <section class="card"><div class="label">Commercial</div><div class="value">{escape(str(score.get("commercial", 0)))}</div></section>
              </div>
            </details>
            """
        )
    return "".join(sections)


@app.get("/topic-packages/{topic_package_id}", response_class=HTMLResponse)
def topic_package_detail_page(
    topic_package_id: str,
    msg: str = "",
    level: str = "ok",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    package_row = db.get(StudioTopicPackage, topic_package_id)
    if not package_row:
        raise HTTPException(status_code=404, detail="topic package not found")
    package = serialize_topic_package(db, package_row, include_items=True, include_audit=True)
    analyses = topic_ai_analyses(db, topic_package_id)
    jobs = topic_ai_jobs(db, topic_package_id)
    topic_intelligence_html = topic_intelligence_versions_html(analyses)
    analyses_html = (
        "<table><thead><tr><th>类型</th><th>Provider</th><th>模型</th><th>Prompt版本</th><th>结果</th><th>时间</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(item["analysis_type"])}</td>'
            f'<td>{escape(item["provider"])}</td>'
            f'<td>{escape(item["model"])}</td>'
            f'<td>{escape(item["prompt_version"])}</td>'
            f'<td><pre>{escape(json.dumps(item["result"], ensure_ascii=False, indent=2))}</pre></td>'
            f'<td>{escape(item.get("updated_at") or "")}</td>'
            "</tr>"
            for item in analyses
        )
        + "</tbody></table>"
        if analyses
        else '<div class="placeholder">暂无 AI Insights。点击 AI分析 后创建任务，再执行待处理任务。</div>'
    )
    jobs_html = (
        "<table><thead><tr><th>任务类型</th><th>状态</th><th>Provider</th><th>模型</th><th>错误</th><th>操作</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(item["job_type"])}</td>'
            f'<td>{escape(item["status"])}</td>'
            f'<td>{escape(item.get("provider") or "")}</td>'
            f'<td>{escape(item.get("model") or "")}</td>'
            f'<td>{escape(item.get("error_message") or "")}</td>'
            f'<td><form method="post" action="/ai/jobs/{escape(item["id"])}/run-form"><input type="hidden" name="topic_package_id" value="{escape(topic_package_id)}"><button class="button secondary" type="submit">执行</button></form></td>'
            "</tr>"
            for item in jobs
        )
        + "</tbody></table>"
        if jobs
        else '<div class="placeholder">暂无 AI 任务</div>'
    )
    similar_html = (
        "<table><thead><tr><th>标题</th><th>原因</th><th>状态</th><th>来源数</th><th>操作</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(item["title"])}</td>'
            f'<td>{escape("; ".join(item.get("reasons") or []))}</td>'
            f'<td>{escape(item["status"])}</td>'
            f'<td>{escape(str(item["source_count"]))}</td>'
            f'<td><a class="button secondary" href="/topic-packages/{escape(item["topic_package_id"])}">查看</a>'
            f'<form method="post" action="/topic-packages/merge-form" onsubmit="return confirm(\'确认合并该主题包到当前主题包？\')"><input type="hidden" name="target_topic_package_id" value="{escape(package["id"])}"><input type="hidden" name="source_topic_package_ids" value="{escape(item["topic_package_id"])}"><button class="button secondary" type="submit">合并到当前</button></form></td>'
            "</tr>"
            for item in package.get("possible_duplicates", [])
        )
        + "</tbody></table>"
        if package.get("possible_duplicates")
        else '<div class="placeholder">暂无疑似相似主题包</div>'
    )
    audit_html = (
        "<table><thead><tr><th>时间</th><th>操作</th><th>变化摘要</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(event.get("created_at") or "")}</td>'
            f'<td>{escape(event.get("action") or "")}</td>'
            f'<td><code>{escape(json.dumps(event.get("metadata") or event.get("after") or {}, ensure_ascii=False))}</code></td>'
            "</tr>"
            for event in package.get("audit_events", [])
        )
        + "</tbody></table>"
        if package.get("audit_events")
        else '<div class="placeholder">暂无审计事件</div>'
    )
    body = f"""
      <h1>{escape(package["title"])}</h1>
      <p class="subtitle"><a href="/topic-packages">返回主题包</a></p>
      {message_html(msg, level)}
      <section class="panel">
        <h2>基本信息</h2>
        <form method="post" action="/topic-packages/{escape(package["id"])}/update-form" class="toolbar">
          <label>标题<br><input class="field" name="title" value="{escape(package["title"])}"></label>
          <label>内容角度<br><input class="field" name="content_angle" value="{escape(package.get("content_angle") or "")}"></label>
          <label>优先级<br><select class="field" name="priority"><option value="{escape(package["priority"])}">{escape(package["priority"])}</option><option value="low">low</option><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option></select></label>
          <label>目标内容<br><input class="field" name="target_content_type" value="{escape(package.get("target_content_type") or "")}"></label>
          <label>目标平台<br><input class="field" name="target_platforms" value="{escape(", ".join(package.get("target_platforms") or []))}"></label>
          <label>摘要<br><textarea class="field" name="summary">{escape(package.get("summary") or "")}</textarea></label>
          <label>备注<br><textarea class="field" name="operator_note">{escape(package.get("operator_note") or "")}</textarea></label>
          <button class="button" type="submit">保存</button>
        </form>
        <div class="actions">
          {topic_package_actions(package["id"])}
        </div>
      </section>
      <section class="panel">
        <h2>聚合统计</h2>
        <div class="grid">
          <section class="card"><div class="label">来源数</div><div class="value">{package["source_count"]}</div></section>
          <section class="card"><div class="label">总评论数</div><div class="value">{package["total_comment_count"]}</div></section>
          <section class="card"><div class="label">平均评分</div><div class="value">{package["average_source_score"] or ""}</div></section>
          <section class="card"><div class="label">最高评分</div><div class="value">{package["max_source_score"] or ""}</div></section>
          <section class="card"><div class="label">风险等级</div><div class="value">{escape(package["risk_level"])}</div></section>
          <section class="card"><div class="label">平台分布</div><div class="value">{escape(json.dumps(package.get("platform_distribution") or {}, ensure_ascii=False))}</div></section>
          <section class="card"><div class="label">风险分布</div><div class="value">{escape(json.dumps(package.get("risk_distribution") or {}, ensure_ascii=False))}</div></section>
        </div>
      </section>
      <section class="panel">
        <h2>添加来源</h2>
        <form method="post" action="/topic-packages/{escape(package["id"])}/items-form" class="toolbar">
          <label>内容项ID，逗号分隔<br><input class="field" name="content_item_ids" placeholder="uuid-1,uuid-2"></label>
          <button class="button" type="submit">添加到主题包</button>
        </form>
      </section>
      <section class="panel">
        <h2>来源内容列表</h2>
        {topic_package_items_table(package)}
      </section>
      <section class="panel">
        <h2>AI Insights</h2>
        <div class="actions">
          <form method="post" action="/topic-packages/{escape(package["id"])}/ai-analyze-form">
            <button class="button" type="submit">AI分析</button>
          </form>
          <form method="post" action="/topic-packages/{escape(package["id"])}/topic-intelligence-form">
            <button class="button" type="submit">生成主题智能分析</button>
          </form>
          <form method="post" action="/topic-packages/{escape(package["id"])}/topic-intelligence-form">
            <button class="button secondary" type="submit">重新分析</button>
          </form>
          <a class="button secondary" href="/gpt-director?topic_package_id={escape(package["id"])}">进入GPT编导</a>
        </div>
        <h3>AI任务</h3>
        {jobs_html}
        <h3>主题智能分析</h3>
        {topic_intelligence_html}
        <h3>分析结果</h3>
        {analyses_html}
      </section>
      <section class="panel">
        <h2>相似主题提示</h2>
        {similar_html}
      </section>
      <section class="panel">
        <h2>人工合并</h2>
        <form method="post" action="/topic-packages/merge-form" class="toolbar" onsubmit="return confirm('确认合并主题包？来源主题包会默认归档。')">
          <input type="hidden" name="target_topic_package_id" value="{escape(package["id"])}">
          <label>来源主题包ID，逗号分隔<br><input class="field" name="source_topic_package_ids"></label>
          <button class="button secondary" type="submit">合并到当前主题包</button>
        </form>
      </section>
      <section class="panel">
        <h2>审计历史</h2>
        {audit_html}
      </section>
    """
    return render_shell("topic-packages", "主题包详情", body)


@app.post("/topic-packages/{topic_package_id}/status-form")
async def topic_package_status_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    try:
        update_topic_package_status(db, topic_package_id, form.get("status", ""))
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=主题包状态已更新", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/update-form")
async def topic_package_update_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    try:
        update_topic_package(
            db,
            topic_package_id,
            TopicPackageUpdate(
                title=form.get("title") or None,
                summary=form.get("summary") or "",
                content_angle=form.get("content_angle") or None,
                priority=form.get("priority") or None,
                target_content_type=form.get("target_content_type") or None,
                target_platforms=[item.strip() for item in form.get("target_platforms", "").split(",") if item.strip()],
                operator_note=form.get("operator_note") or None,
            ),
        )
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=主题包已更新", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/items-form")
async def topic_package_items_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    ids = [item.strip() for item in form.get("content_item_ids", "").split(",") if item.strip()]
    try:
        result = add_items_to_topic_package(db, topic_package_id, ids)
        db.commit()
        added = sum(1 for item in result["results"] if item["status"] in {"added", "restored"})
        duplicates = sum(1 for item in result["results"] if item["status"] == "duplicate")
        return RedirectResponse(
            f"/topic-packages/{topic_package_id}?msg={quote(f'来源已处理：新增/恢复 {added}，重复 {duplicates}')}",
            status_code=303,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/remove-item-form")
async def topic_package_remove_item_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    try:
        remove_item_from_topic_package(db, topic_package_id, form.get("content_item_id", ""))
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=来源已移除", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/primary-item-form")
async def topic_package_primary_item_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    try:
        set_primary_item(db, topic_package_id, form.get("content_item_id", ""))
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=主要来源已更新", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/move-item-form")
async def topic_package_move_item_form(topic_package_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    content_item_id = form.get("content_item_id", "")
    direction = form.get("direction", "")
    try:
        package = db.get(StudioTopicPackage, topic_package_id)
        if not package:
            raise HTTPException(status_code=404, detail="topic package not found")
        current = serialize_topic_package(db, package, include_items=True)
        ordered = [item["content_item_id"] for item in current.get("items", [])]
        index = ordered.index(content_item_id)
        swap_with = index - 1 if direction == "up" else index + 1
        if 0 <= swap_with < len(ordered):
            ordered[index], ordered[swap_with] = ordered[swap_with], ordered[index]
            reorder_topic_items(db, topic_package_id, ordered)
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=排序已更新", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/merge-form")
async def topic_package_merge_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    target_id = form.get("target_topic_package_id", "")
    source_ids = [item.strip() for item in form.get("source_topic_package_ids", "").split(",") if item.strip()]
    try:
        merge_topic_packages(db, target_id, source_ids, archive_sources=True)
        db.commit()
        return RedirectResponse(f"/topic-packages/{target_id}?msg=主题包已合并", status_code=303)
    except Exception as exc:
        db.rollback()
        target = target_id or ""
        return RedirectResponse(f"/topic-packages/{target}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.get("/api/ai/health")
def ai_health_api() -> dict:
    return ai_health_payload()


@app.get("/api/prompt-templates")
def prompt_templates_api(category: str = "", enabled: Optional[bool] = None, db: Session = Depends(get_db)) -> dict:
    return {"items": list_prompt_templates(db, category or None, enabled)}


@app.post("/api/prompt-templates")
def create_prompt_template_api(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    row = create_prompt_template(db, payload)
    db.commit()
    return serialize_prompt_template(row)


@app.post("/api/topic-packages/{topic_package_id}/ai-jobs")
def create_topic_ai_jobs_api(topic_package_id: str, job_type: str = "all", db: Session = Depends(get_db)) -> dict:
    if job_type == "all":
        rows = create_default_topic_ai_jobs(db, topic_package_id)
    else:
        rows = [create_ai_job(db, topic_package_id, job_type)]
    db.commit()
    return {"items": [serialize_ai_job(row) for row in rows]}


@app.get("/api/topic-packages/{topic_package_id}/ai-jobs")
def topic_ai_jobs_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    return {"items": topic_ai_jobs(db, topic_package_id)}


@app.post("/api/ai/jobs/{job_id}/run")
def run_ai_job_api(job_id: str, db: Session = Depends(get_db)) -> dict:
    row = run_ai_job(db, job_id)
    db.commit()
    return serialize_ai_job(row)


@app.get("/api/topic-packages/{topic_package_id}/ai-analyses")
def topic_ai_analyses_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    return {"items": topic_ai_analyses(db, topic_package_id)}


@app.get("/api/topic-packages/{topic_package_id}/editorial-prompt")
def topic_editorial_prompt_api(topic_package_id: str, db: Session = Depends(get_db)) -> dict:
    return build_editorial_prompt(db, topic_package_id)


@app.post("/topic-packages/{topic_package_id}/ai-analyze-form")
async def topic_ai_analyze_form(topic_package_id: str, db: Session = Depends(get_db)):
    try:
        create_default_topic_ai_jobs(db, topic_package_id)
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=AI任务已创建", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/topic-packages/{topic_package_id}/topic-intelligence-form")
async def topic_intelligence_form(topic_package_id: str, db: Session = Depends(get_db)):
    try:
        create_ai_job(db, topic_package_id, TOPIC_INTELLIGENCE_JOB_TYPE)
        db.commit()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg=主题智能分析任务已创建", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/ai/jobs/{job_id}/run-form")
async def ai_job_run_form(job_id: str, request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    topic_package_id = form.get("topic_package_id", "")
    try:
        row = run_ai_job(db, job_id)
        db.commit()
        msg = "AI任务已完成" if row.status == "completed" else f"AI任务状态：{row.status}"
        return RedirectResponse(f"/topic-packages/{topic_package_id}?msg={quote(msg)}", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/topic-packages/{topic_package_id}?level=warn&msg={quote(str(exc))}", status_code=303)


@app.get("/gpt-director", response_class=HTMLResponse)
def gpt_director_page(
    topic_package_id: str = "",
    generate: int = 0,
    msg: str = "",
    level: str = "ok",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    packages = list_topic_packages(db, limit=100)["items"]
    selected_id = topic_package_id or (packages[0]["id"] if packages else "")
    selected = db.get(StudioTopicPackage, selected_id) if selected_id else None
    context = {}
    prompt_payload = {}
    prompt_text = ""
    prompt_template_id = ""
    context_notice = ""
    if selected_id:
        try:
            context = editorial_context(db, selected_id)
            if generate:
                prompt_payload = build_editorial_prompt(db, selected_id)
                prompt_text = prompt_payload["prompt"]
                prompt_template_id = prompt_payload["prompt_template_id"]
        except Exception as exc:
            context_notice = str(exc)
    saved_briefs = []
    if selected_id:
        saved_briefs = [
            serialize_editorial_brief(row)
            for row in db.scalars(
            select(StudioEditorialBrief)
            .where(StudioEditorialBrief.topic_package_id == selected_id)
                .order_by(StudioEditorialBrief.created_at.desc())
            .limit(20)
            ).all()
        ]
    options = "".join(
        f'<option value="{escape(package["id"])}" {"selected" if package["id"] == selected_id else ""}>{escape(package["title"])}</option>'
        for package in packages
    )
    topic_context = context.get("topic_package") or {}
    intelligence = context.get("topic_intelligence") or {}
    audience = intelligence.get("audience") or {}
    platform_distribution = topic_context.get("platform_distribution") or {}
    pain_points = intelligence.get("pain_points") or []
    quotes = intelligence.get("user_quotes") or []
    opportunities = intelligence.get("content_opportunities") or []
    pain_html = (
        "<table><thead><tr><th>问题</th><th>频率</th><th>情绪</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(str(row.get("problem") or ""))}</td>'
            f'<td>{escape(str(row.get("frequency") or ""))}</td>'
            f'<td>{escape(str(row.get("emotion") or ""))}</td>'
            "</tr>"
            for row in pain_points
            if isinstance(row, dict)
        )
        + "</tbody></table>"
        if pain_points
        else '<div class="placeholder">暂无痛点分析</div>'
    )
    quotes_html = (
        "<table><thead><tr><th>用户原话</th><th>来源</th><th>互动</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(str(row.get("quote") or ""))}</td>'
            f'<td>{escape(str(row.get("source") or ""))}</td>'
            f'<td>{escape(str(row.get("engagement") or 0))}</td>'
            "</tr>"
            for row in quotes
            if isinstance(row, dict)
        )
        + "</tbody></table>"
        if quotes
        else '<div class="placeholder">暂无用户原话</div>'
    )
    opportunities_html = (
        "<table><thead><tr><th>角度</th><th>理由</th><th>形式</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>{escape(str(row.get("angle") or ""))}</td>'
            f'<td>{escape(str(row.get("reason") or ""))}</td>'
            f'<td>{escape(str(row.get("recommended_format") or ""))}</td>'
            "</tr>"
            for row in opportunities
            if isinstance(row, dict)
        )
        + "</tbody></table>"
        if opportunities
        else '<div class="placeholder">暂无内容机会</div>'
    )
    briefs_html = (
        "<table><thead><tr><th>版本</th><th>状态</th><th>创建人</th><th>创建时间</th><th>标题</th><th>Hook</th><th>内容</th><th>操作</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f'<td>Version {escape(row["version"])}</td>'
            f'<td>{escape(row["status"])}</td>'
            f'<td>{escape(row.get("created_by") or "")}</td>'
            f'<td>{escape(row.get("created_at") or "")}</td>'
            f'<td>{escape(str((row.get("output") or {}).get("title") or ""))}</td>'
            f'<td>{escape(str((row.get("output") or {}).get("hook") or ""))}</td>'
            f'<td><details><summary>查看旧版本</summary><pre>{escape(json.dumps(row.get("output") or {}, ensure_ascii=False, indent=2))}</pre></details></td>'
            '<td><div class="actions">'
            f'<form method="post" action="/gpt-director/brief-status-form"><input type="hidden" name="topic_package_id" value="{escape(selected_id)}"><input type="hidden" name="brief_id" value="{escape(row["id"])}"><input type="hidden" name="status" value="reviewing"><button class="button secondary" type="submit">进入审核</button></form>'
            f'<form method="post" action="/gpt-director/brief-status-form"><input type="hidden" name="topic_package_id" value="{escape(selected_id)}"><input type="hidden" name="brief_id" value="{escape(row["id"])}"><input type="hidden" name="status" value="approved"><button class="button" type="submit">批准</button></form>'
            "</div></td>"
            "</tr>"
            for row in saved_briefs
        )
        + "</tbody></table>"
        if saved_briefs
        else '<div class="placeholder">暂无 Editorial Brief 版本</div>'
    )
    prompt_notice = message_html(context_notice, "warn") if context_notice else ""
    prompt_form_action = f"/gpt-director?topic_package_id={escape(selected_id)}&generate=1"
    body = f"""
      <h1>GPT编导</h1>
      <p class="subtitle">Editorial Studio：整理 AI 分析结果，生成可复制给 ChatGPT 的 Prompt，并保存人工粘贴回来的视频编导 JSON。</p>
      {message_html(msg, level)}
      <section class="panel">
        <form method="get" action="/gpt-director" class="toolbar">
          <label>选择主题包<br><select class="field" name="topic_package_id">{options}</select></label>
          <button class="button secondary" type="submit">加载</button>
        </form>
      </section>
      <section class="panel">
        <h2>素材上下文</h2>
        {prompt_notice}
        <div class="detail-grid">
          <div>主题包</div><div>{escape(selected.title if selected else "")}</div>
          <div>来源数量</div><div>{escape(str(topic_context.get("source_count") or ""))}</div>
          <div>平台分布</div><div>{escape(json.dumps(platform_distribution, ensure_ascii=False))}</div>
          <div>核心总结</div><div>{escape(str(intelligence.get("core_summary") or ""))}</div>
          <div>用户画像</div><div>{escape(str(audience.get("persona") or ""))}</div>
        </div>
        <h3>痛点</h3>
        {pain_html}
        <h3>用户原话</h3>
        {quotes_html}
        <h3>内容机会</h3>
        {opportunities_html}
      </section>
      <section class="panel">
        <h2>生成GPT Prompt</h2>
        <form method="get" action="/gpt-director" class="toolbar">
          <input type="hidden" name="topic_package_id" value="{escape(selected_id)}">
          <input type="hidden" name="generate" value="1">
          <button class="button" type="submit">生成GPT Prompt</button>
        </form>
        <textarea id="gpt-prompt" class="field" style="width: 100%; min-height: 340px;">{escape(prompt_text)}</textarea>
        <button class="button secondary" type="button" onclick="navigator.clipboard && navigator.clipboard.writeText(document.getElementById('gpt-prompt').value)">复制Prompt</button>
      </section>
      <section class="panel">
        <h2>GPT结果输入</h2>
        <form method="post" action="/gpt-director/save-brief-form" class="toolbar">
          <input type="hidden" name="topic_package_id" value="{escape(selected_id)}">
          <input type="hidden" name="prompt_snapshot" value="{escape(prompt_text)}">
          <input type="hidden" name="prompt_template_id" value="{escape(prompt_template_id)}">
          <label style="width:100%">GPT Output JSON<br><textarea class="field" style="width:100%; min-height:220px;" name="output_json">{{}}</textarea></label>
          <button class="button" type="submit">解析并保存</button>
        </form>
      </section>
      <section class="panel">
        <h2>Editorial Brief 历史版本</h2>
        {briefs_html}
      </section>
    """
    return render_shell("gpt-director", "GPT编导", body)


@app.post("/gpt-director/save-brief-form")
async def gpt_director_save_brief_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    topic_package_id = form.get("topic_package_id", "")
    try:
        save_editorial_output(
            db,
            topic_package_id,
            form.get("prompt_snapshot", ""),
            form.get("output_json", "{}"),
            prompt_template_id=form.get("prompt_template_id") or None,
            created_by="operator",
            status="draft",
        )
        db.commit()
        return RedirectResponse(f"/gpt-director?topic_package_id={topic_package_id}&msg=Editorial Brief 版本已保存", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/gpt-director?topic_package_id={topic_package_id}&level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/gpt-director/brief-status-form")
async def gpt_director_brief_status_form(request: Request, db: Session = Depends(get_db)):
    form = await parse_urlencoded(request)
    topic_package_id = form.get("topic_package_id", "")
    try:
        update_editorial_brief_status(db, form.get("brief_id", ""), form.get("status", ""))
        db.commit()
        return RedirectResponse(f"/gpt-director?topic_package_id={topic_package_id}&msg=Editorial Brief 状态已更新", status_code=303)
    except Exception as exc:
        db.rollback()
        return RedirectResponse(f"/gpt-director?topic_package_id={topic_package_id}&level=warn&msg={quote(str(exc))}", status_code=303)


@app.post("/api/editorial-briefs")
def create_editorial_brief_api(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    output_value = payload.get("output_json") if "output_json" in payload else payload.get("input_json", "{}")
    output_text = output_value if isinstance(output_value, str) else json.dumps(output_value, ensure_ascii=False)
    row = save_editorial_output(
        db,
        str(payload.get("topic_package_id") or ""),
        str(payload.get("prompt_snapshot") or ""),
        output_text,
        prompt_template_id=payload.get("prompt_template_id"),
        created_by=str(payload.get("created_by") or "operator"),
        status=str(payload.get("status") or "draft"),
    )
    db.commit()
    return serialize_editorial_brief(row)


@app.patch("/api/editorial-briefs/{brief_id}/status")
def update_editorial_brief_status_api(brief_id: str, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    row = update_editorial_brief_status(db, brief_id, str(payload.get("status") or ""))
    db.commit()
    return serialize_editorial_brief(row)


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
