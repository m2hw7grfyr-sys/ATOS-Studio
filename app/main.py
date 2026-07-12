from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from config.settings import get_settings
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
    "content-pool": "内容池",
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


@app.get("/content-pool", response_class=HTMLResponse)
def content_pool() -> HTMLResponse:
    return placeholder_page("content-pool")


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

