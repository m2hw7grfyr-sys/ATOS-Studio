# ATOS Studio

ATOS Studio is an independent companion repository for ATOS. Sprint 02 adds the first content-pool loop:

```text
ATOS posts -> ATOS read-only Studio API -> Studio manual import -> studio_content_items -> content pool page
```

Sprint 03 adds active ATOS push:

```text
ATOS Post Pool -> ATOS backend proxy -> Studio push API -> studio_content_items -> ATOS status feedback
```

Sprint 04 adds manual review and topic packages:

```text
studio_content_items -> manual review -> studio_topic_packages -> package approval
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
STUDIO_PUSH_AUTH_ENABLED=true
STUDIO_PUSH_API_TOKEN=replace-with-the-same-token
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

Push from ATOS backend:

```bash
curl -X POST http://127.0.0.1:8502/api/content-items/push \
  -H "Authorization: Bearer replace-with-the-same-token" \
  -H "Content-Type: application/json" \
  -d '{"source_platform":"reddit","atos_post_id":"1","source_post_id":"abc123","title":"Example","body":"Body","push_context":{"requested_content_type":"video","target_platforms":["tiktok"],"operator_note":""}}'
```

Source status:

```bash
curl -H "Authorization: Bearer replace-with-the-same-token" \
  "http://127.0.0.1:8502/api/content-items/source-status?source_platform=reddit&source_post_id=abc123"
```

List content items:

```bash
curl "http://127.0.0.1:8502/api/content-items?status=pending_review&limit=50&offset=0"
```

Update status:

```bash
curl -X PATCH http://127.0.0.1:8502/api/content-items/{studio_item_id}/status \
  -H "Content-Type: application/json" \
  -d '{"status":"approved","review_note":"ready for short video"}'
```

Batch status update:

```bash
curl -X POST http://127.0.0.1:8502/api/content-items/status-batch \
  -H "Content-Type: application/json" \
  -d '{"content_item_ids":["uuid-1","uuid-2"],"status":"approved","review_note":"适合后续做短视频"}'
```

Create a topic package from content items:

```bash
curl -X POST http://127.0.0.1:8502/api/topic-packages/from-content-items \
  -H "Content-Type: application/json" \
  -d '{"title":"ADHD medication wears off too early","content_item_ids":["uuid-1","uuid-2"],"content_angle":"解释型","target_content_type":"video","target_platforms":["tiktok","youtube_shorts"]}'
```

Topic package APIs:

```text
GET    /api/topic-packages
GET    /api/topic-packages/{topic_package_id}
POST   /api/topic-packages
PATCH  /api/topic-packages/{topic_package_id}
PATCH  /api/topic-packages/{topic_package_id}/status
DELETE /api/topic-packages/{topic_package_id}
POST   /api/topic-packages/{topic_package_id}/items
DELETE /api/topic-packages/{topic_package_id}/items/{content_item_id}
PATCH  /api/topic-packages/{topic_package_id}/primary-item
PATCH  /api/topic-packages/{topic_package_id}/items/order
GET    /api/topic-packages/similar?title=...
POST   /api/topic-packages/merge
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
- Source type, requested content type, target platforms, push count, and last pushed time
- Actions: view, approve, reject, archive, create topic package
- Batch actions: approve, reject, archive, restore to pending review, create topic package

## Topic Packages

A topic package is a manually curated group of source content around one pain point, question, or content angle. It is not a video project and does not trigger generation.

Current states:

- `pending_review`
- `approved`
- `rejected`
- `archived`

Member rules:

- One content item cannot appear twice in the same package.
- One content item may belong to multiple packages.
- Removing a member sets `removed_at`; it does not delete the content item.
- If the removed member was primary, the service selects the next active source as primary when available.
- Ordering is stored in `position`.

Statistics are recalculated by the service after membership changes:

- `source_count`
- `total_comment_count`
- `average_source_score`
- `max_source_score`
- `risk_level`

Risk aggregation:

- Any source `high` -> package `high`
- Else any source `medium` -> package `medium`
- Else all active sources `low` -> package `low`
- Else `unknown`

Similarity hints use normalized title and token overlap only. They are marked as possible duplicates and never block creation.

Audit events are recorded for review changes, package creation, updates, status changes, member add/remove, primary source changes, sorting, and merge.

Open pages:

```text
http://127.0.0.1:8502/content-pool
http://127.0.0.1:8502/topic-packages
```

## Idempotency

Duplicate imports do not create another row. Priority:

1. `source_platform + source_post_id`
2. `atos_post_id`
3. normalized `source_url`
4. content hash fallback

The original ATOS response is stored in `source_snapshot_json` on import.

Sprint 03 stores ATOS push context in the same table and uses `source_type=atos_manual_push`.

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
