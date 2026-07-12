# ATOS Studio

ATOS Studio is an independent companion repository for ATOS. Sprint 02 adds the first content-pool loop:

```text
ATOS posts -> ATOS read-only Studio API -> Studio manual import -> studio_content_items -> content pool page
```

Video generation, ComfyUI, Wan, TTS, subtitles, FFmpeg, cloud backup, automatic ingestion, clustering, and shared user login are not implemented.

## Environment

- Python 3.12 is recommended to match the ATOS backend Dockerfile.
- Current local tests also run on Python 3.9.
- ATOS backend default port: `8000`.
- ATOS Studio default port: `8502`.

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

Use the same token value in ATOS and Studio:

```env
ATOS_BASE_URL=http://127.0.0.1:8000
ATOS_STUDIO_API_TOKEN=replace-with-the-same-token
ATOS_REQUEST_TIMEOUT_SECONDS=10
STUDIO_DATABASE_URL=sqlite:///./storage/atos_studio.db
```

Do not commit `.env`.

## Migrate

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
.venv/bin/alembic upgrade head
```

Local SQLite database path:

```text
storage/atos_studio.db
```

## Start

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8502 --reload
```

Open:

```text
http://127.0.0.1:8502/content-pool
```

## API

Health:

```bash
curl http://127.0.0.1:8502/health
```

Import from ATOS:

```bash
curl -X POST http://127.0.0.1:8502/api/content-items/import \
  -H "Content-Type: application/json" \
  -d '{"source_platform":"reddit","source_post_id":"abc123"}'
```

List content items:

```bash
curl "http://127.0.0.1:8502/api/content-items?status=pending_review&limit=50&offset=0"
```

Update status:

```bash
curl -X PATCH http://127.0.0.1:8502/api/content-items/{studio_item_id}/status \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'
```

Allowed statuses:

- `pending_review`
- `approved`
- `rejected`
- `archived`

## Content Pool

The content pool page includes:

- ATOS connection status: `Connected`, `Authentication failed`, `Unavailable`, or `Not configured`
- Manual ATOS import by platform and post ID/source post ID
- List with title, platform, author, score, comments, risk level, status, imported time
- Detail page with source snapshot
- Actions: view, approve, reject, archive

## Idempotency

Duplicate imports do not create another row. Priority:

1. `source_platform + source_post_id`
2. `atos_post_id`
3. normalized `source_url`
4. content hash fallback

The original ATOS response is stored in `source_snapshot_json` on import.

## SQLite And PostgreSQL

SQLite is the local default and stores JSON fields as text columns. PostgreSQL can be used by changing `STUDIO_DATABASE_URL`; the current migration avoids SQLite-only column types, so it remains portable. PostgreSQL deployments should run the same Alembic migration command and should not point `STUDIO_DATABASE_URL` at the ATOS core database unless only Studio-owned `studio_` tables are used.

## Restore Local Test Database

To reset the local Studio database:

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
rm storage/atos_studio.db
.venv/bin/alembic upgrade head
```

`storage/*.db` is ignored by Git.

## Test

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
PYTHONPATH=. .venv/bin/python -m unittest discover tests
```

## Relationship With ATOS

ATOS owns collection, post storage, scoring, reply operations, and source data. Studio owns content-pool records, source snapshots, video-oriented project state, assets, generated outputs, and backup records.

Studio reads ATOS through the ATOS `/api/studio` read-only API. Studio does not write ATOS databases or mutate ATOS post status.

## Common Errors

`ATOS鉴权失败`

The Studio `ATOS_STUDIO_API_TOKEN` does not match ATOS `ATOS_STUDIO_API_TOKEN`.

`ATOS服务不可达`

ATOS is not running at `ATOS_BASE_URL`, or the port is wrong.

`no such table: studio_content_items`

Run `.venv/bin/alembic upgrade head`.

`Address already in use`

Use another port, for example `--port 8503`, or stop the existing local process.

