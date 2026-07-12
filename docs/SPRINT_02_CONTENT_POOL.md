# Sprint 02 Content Pool

## Implemented

- ATOS read-only Studio API:
  - `GET /api/studio/health`
  - `GET /api/studio/content-items`
  - `GET /api/studio/content-items/{source_post_id}`
- ATOS machine authentication with `Authorization: Bearer <token>`.
- Studio SQLAlchemy database layer.
- Studio Alembic migration for `studio_content_items`.
- Studio ATOS client with timeout, auth error, not-found, and unavailable errors.
- Studio manual import API.
- Studio content pool API and HTML page.
- Real homepage status checks for ATOS and Studio database.

## Start ATOS

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS
ATOS_STUDIO_AUTH_ENABLED=true \
ATOS_STUDIO_API_TOKEN=replace-with-a-strong-token \
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If `8000` is occupied, use another port and set Studio `ATOS_BASE_URL` to match.

## Start Studio

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
.venv/bin/alembic upgrade head
ATOS_BASE_URL=http://127.0.0.1:8000 \
ATOS_STUDIO_API_TOKEN=replace-with-the-same-token \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8502
```

## Manual Import Flow

1. Open `http://127.0.0.1:8502/content-pool`.
2. Enter platform, for example `reddit`.
3. Enter an ATOS `posts.id`, `posts.uuid`, or platform `source_post_id`.
4. Click `从ATOS导入`.
5. Studio calls ATOS `/api/studio/content-items/{source_post_id}`.
6. Studio writes one row to `studio_content_items`.
7. Repeating the import returns the existing item and does not create a duplicate.

## Idempotency

Priority:

1. `source_platform + source_post_id`
2. `atos_post_id`
3. normalized `source_url`
4. content hash fallback

The table enforces uniqueness with `source_platform + source_post_id` and `source_hash`.

Sprint 03 extends the same table for ATOS active push. It adds push context fields and uses `source_type=atos_manual_push`; Sprint 02 manual import remains `source_type=manual_import`.

## Table Summary

`studio_content_items` stores:

- Studio primary key `id`
- ATOS/source identifiers
- title/body/author/source URL
- published and collected timestamps
- source score, comments, risk level
- JSON text for tags, metadata, and original source snapshot
- source hash
- status
- source type
- imported/created/updated timestamps

## API Examples

ATOS:

```bash
curl -H "Authorization: Bearer replace-with-a-strong-token" \
  "http://127.0.0.1:8000/api/studio/content-items?limit=50&offset=0"
```

Studio import:

```bash
curl -X POST http://127.0.0.1:8502/api/content-items/import \
  -H "Content-Type: application/json" \
  -d '{"source_platform":"reddit","source_post_id":"abc123"}'
```

Studio approve:

```bash
curl -X PATCH http://127.0.0.1:8502/api/content-items/{studio_item_id}/status \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'
```

## Current Limits

- No automatic ATOS-to-Studio ingestion.
- No theme clustering.
- No GPT director workspace.
- No video generation.
- No ComfyUI, Wan, TTS, subtitles, FFmpeg, or backup provider.
- No formal user login.
- ATOS `risk_level` is currently returned as `null` because the ATOS post model has no native risk-level column.

## Troubleshooting

`Authentication failed`

Studio token does not match ATOS token.

`Unavailable`

ATOS is not running or `ATOS_BASE_URL` points to the wrong port.

`no such table: studio_content_items`

Run `.venv/bin/alembic upgrade head` in `ATOS-Studio`.

## SQLite And PostgreSQL

SQLite is the default local database. JSON-like fields are stored as text for portability. PostgreSQL can be used by setting `STUDIO_DATABASE_URL` to a PostgreSQL SQLAlchemy URL and running Alembic.

## Reset Local Studio Database

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
rm storage/atos_studio.db
.venv/bin/alembic upgrade head
```

Do not use production ATOS databases for destructive tests.
