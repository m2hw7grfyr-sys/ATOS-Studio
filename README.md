# ATOS Studio

ATOS Studio is a separate companion application for ATOS. Sprint 01 creates the independent repository, audits the current ATOS architecture, and defines the integration boundary. It does not implement video generation, ComfyUI, Wan, TTS, subtitles, backups, or a complete content pool.

## Current Scope

- Minimal FastAPI application shell
- Home page with service and integration status
- Left navigation placeholders
- `GET /health`
- Environment-based configuration
- ATOS architecture audit document
- ATOS Studio integration protocol document
- Basic automated tests

## Environment Requirements

- Python 3.12 is recommended to match the ATOS backend Dockerfile.
- Python 3.9+ can run the current minimal code in local testing.
- No ComfyUI or GPU Worker is required for Sprint 01.

## Install

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configure

```bash
cp .env.example .env
```

Do not commit `.env`. The file is ignored by Git.

Important settings:

- `ATOS_BASE_URL`: ATOS backend URL, default `http://127.0.0.1:8000`
- `ATOS_DATABASE_URL`: optional read-only reference, not required in Sprint 01
- `STUDIO_DATABASE_URL`: Studio database URL, default SQLite
- `STUDIO_STORAGE_ROOT`: Studio storage directory
- `STUDIO_PORT`: default `8502`
- `COMFYUI_BASE_URL`: optional, may remain empty
- `GPU_WORKER_URL`: optional, may remain empty
- `BACKUP_PROVIDER`: default `none`
- `BACKUP_TARGET`: optional
- `LOG_LEVEL`: default `INFO`

## Start

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8502 --reload
```

Equivalent helper:

```bash
scripts/run_dev.sh
```

Open:

```text
http://127.0.0.1:8502
```

Health check:

```text
http://127.0.0.1:8502/health
```

Expected response:

```json
{
  "service": "atos-studio",
  "status": "ok",
  "version": "0.1.0"
}
```

## Test

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
PYTHONPATH=. .venv/bin/python -m unittest discover tests
```

## Current Pages

- 首页
- 灵感中心
- 内容池
- 视频项目
- 生成队列
- 素材库
- 成片库
- Studio设置

All non-home pages are placeholders and display `该模块将在后续Sprint实现`.

## Relationship With ATOS

ATOS remains responsible for collection, source posts, comments/source data, AI scoring, reply operations, and original topic data. Studio will own video-oriented content pools, projects, storyboards, generation jobs, media assets, finished renders, and backup records.

Recommended integration mode for future sprints: ATOS internal API first. Studio should not directly modify ATOS core tables. Studio-owned tables should use the `studio_` prefix.

## Not Implemented

- Video generation
- ComfyUI integration
- Wan integration
- TTS
- Subtitles
- Backup providers
- Full content pool CRUD
- Automatic ATOS-to-Studio ingestion
- Shared login
- Studio database migrations

## Common Errors

`ModuleNotFoundError: No module named 'fastapi'`

Install dependencies with `.venv/bin/pip install -r requirements.txt`.

`Address already in use`

Change `STUDIO_PORT` or start uvicorn with another `--port`.

`ComfyUI Not configured` or `GPU Worker Not configured`

This is expected in Sprint 01 and does not block startup.

`ATOS connection status shows Configured but ATOS is not running`

Sprint 01 only confirms that `ATOS_BASE_URL` is configured. Active ATOS API probing is reserved for a later integration sprint.

