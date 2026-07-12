# Sprint 03 ATOS Push

## Goal

Sprint 03 adds active ATOS-to-Studio push:

```text
ATOS Post Pool
  ↓
ATOS backend proxy
  ↓
Studio push API
  ↓
studio_content_items
  ↓
ATOS Studio status feedback
```

## Push API

```text
POST /api/content-items/push
Authorization: Bearer <STUDIO_PUSH_API_TOKEN>
```

The API creates a content-pool item or returns the existing item if it is a duplicate.

## Source Status API

```text
GET  /api/content-items/source-status
POST /api/content-items/source-status/batch
```

Both endpoints use the same push token.

## Authentication

```env
STUDIO_PUSH_AUTH_ENABLED=true
STUDIO_PUSH_API_TOKEN=replace-with-the-same-token
```

Development can explicitly disable auth with `STUDIO_PUSH_AUTH_ENABLED=false`. Non-development environments must keep auth enabled.

## Idempotency

Duplicate priority:

1. `source_platform + source_post_id`
2. `atos_post_id`
3. normalized `source_url`
4. `source_hash`

Repeated pushes do not create a second row and do not reset an approved/rejected/archived item to `pending_review`.

On duplicate push, Studio updates only non-destructive fields:

- `last_pushed_at`
- `push_count`
- target content context
- last source snapshot

## Added Fields

`studio_content_items` now includes:

- `requested_content_type`
- `target_platforms_json`
- `operator_note`
- `last_pushed_at`
- `push_count`

Source type used by this sprint:

```text
atos_manual_push
```

Existing source type remains:

```text
manual_import
```

## Page Changes

Content Pool list shows:

- Source type
- Target content type
- Target platforms
- Push count
- Last pushed time

Content detail shows:

- ATOS push context
- First imported time
- Last pushed time
- Push count
- Source snapshot

Home shows lightweight content-pool statistics:

- Total content items
- Pending review count
- ATOS manual push count
- Today's new count

## Migration

```bash
.venv/bin/alembic upgrade head
```

Migration:

```text
0002_add_atos_push_fields
```

## Tests

```bash
.venv/bin/python -m pytest tests/test_app.py -q
```

Covered:

- Valid token push
- Missing token 401
- Wrong token 401
- First push 201
- Duplicate push 200
- Duplicate push does not reset approved status
- Push count increments
- Source status query
- Batch source status query
- Invalid payload 422

## Not Implemented

- Automatic ingestion
- Topic clustering
- Video projects
- GPT script workspace
- ComfyUI
- TTS
- Subtitles
- FFmpeg
- Cloud backup
- Formal user login
