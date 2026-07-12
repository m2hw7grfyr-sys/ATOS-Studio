# ATOS Studio Integration Protocol

Sprint: Studio Sprint 02
Version: 0.1.0

## Ownership Boundary

ATOS is responsible for:

- Data collection
- Post and comment/source-content storage
- AI scoring and analysis
- Reply operations
- Raw topic/source data
- Providing content sources to Studio

Studio is responsible for:

- Content pool
- Asset organization
- GPT director/script exchange
- Video projects
- Storyboards
- Generation jobs
- Media files
- Finished videos
- Backup records

## Integration Principles

- ATOS and Studio remain independent code repositories.
- Studio must not directly modify ATOS core business logic.
- Studio-owned database tables must use the `studio_` prefix.
- ATOS posts must be associated through stable IDs, preferably ATOS `posts.uuid` plus platform/source IDs.
- Sending the same post to Studio more than once must be detectable.
- Later sprints may support both manual send-to-Studio and automatic pool ingestion.
- Sprint 02 implements manual import only. It does not implement automatic ingestion.
- Missing optional generation services, including GPU Worker and ComfyUI, must not prevent Studio startup.

## Recommended Mode

Use ATOS internal APIs for ATOS-owned content and let Studio own future `studio_` data.

Direct shared database access is not recommended for ATOS core tables because it would couple two release cycles and allow Studio to bypass ATOS lifecycle rules. A future mixed deployment may place `studio_` tables in the same database instance, but those tables must remain Studio-owned.

## Implemented ATOS Read-Only API

ATOS now exposes a read-only Studio API under `/api/studio`.

Authentication:

```http
Authorization: Bearer <ATOS_STUDIO_API_TOKEN>
```

ATOS configuration:

```env
ATOS_STUDIO_AUTH_ENABLED=true
ATOS_STUDIO_API_TOKEN=replace-with-a-strong-token
```

Studio configuration:

```env
ATOS_BASE_URL=http://127.0.0.1:8000
ATOS_STUDIO_API_TOKEN=replace-with-the-same-token
```

### Health

`GET /api/studio/health`

```json
{
  "service": "atos-studio-api",
  "status": "ok",
  "api_version": "1"
}
```

### List Content Items

`GET /api/studio/content-items`

Supported query parameters:

- `platform`
- `min_score`
- `risk_level`
- `search`
- `created_after`
- `created_before`
- `limit`, default `50`, max `200`
- `offset`, default `0`

Response shape:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

### Get Content Item

`GET /api/studio/content-items/{source_post_id}`

The lookup accepts ATOS `posts.uuid`, ATOS numeric `posts.id`, or platform `source_post_id`. The response includes both ATOS and platform identifiers.

```json
{
  "atos_post_id": "1",
  "atos_post_uuid": "uuid",
  "source_platform": "reddit",
  "source_post_id": "abc123",
  "source_url": "https://example.com/post",
  "title": "post title",
  "body": "post body",
  "author": "author",
  "published_at": null,
  "collected_at": "2026-07-12T00:00:00",
  "score": 0,
  "comment_count": 0,
  "risk_level": null,
  "tags": [],
  "metadata": {}
}
```

ATOS currently does not have a native post `risk_level` column, so `risk_level` is returned as `null`.

## Studio Content Pool API

### Import From ATOS

`POST /api/content-items/import`

Request:

```json
{
  "source_platform": "reddit",
  "source_post_id": "abc123"
}
```

First import returns `201 Created`:

```json
{
  "created": true,
  "duplicate": false,
  "item": {}
}
```

Duplicate import returns `200 OK`:

```json
{
  "created": false,
  "duplicate": true,
  "item": {}
}
```

### Studio Content Items

- `GET /api/content-items`
- `GET /api/content-items/{studio_item_id}`
- `PATCH /api/content-items/{studio_item_id}/status`

Allowed statuses: `pending_review`, `approved`, `rejected`, `archived`.

## Idempotency

Preferred idempotency key:

```text
{source_platform}:{source_post_id}
```

Fallback when `source_post_id` is missing:

```text
{source_platform}:{normalized_source_url_hash}
```

Optional stronger key when ATOS provides a stable internal ID:

```text
atos:{atos_post_uuid}
```

Duplicate handling:

- If the idempotency key already exists, Studio returns the existing content item.
- Duplicate requests must not create a second content item.
- If the new payload contains additional non-empty fields, a future sprint may merge metadata. Sprint 02 returns the existing item unchanged.

## Missing Data Handling

- `source_platform` is required.
- At least one of `source_post_id`, `atos_post_id`, or `source_url` is required.
- Empty `title` is allowed only if `body` is present.
- Empty `body` is allowed only if `title` is present.
- Missing `published_at` should be stored as null.
- Missing `score`, `comment_count`, `tags`, and `metadata` should default to `0`, `0`, `[]`, and `{}`.
- Unknown `risk_level` should be stored as `unknown` or rejected with a validation error in a later implementation.

## Version Mismatch Handling

- Requests should include an API version header in a future sprint, for example `X-ATOS-Studio-Protocol-Version: 0.1`.
- Studio should return `426 Upgrade Required` or `409 Conflict` if ATOS sends a payload from an incompatible future protocol.
- Backward-compatible optional fields should be ignored or stored under `metadata`.
- Breaking field changes require a new protocol version.

## Authentication

Sprint 02 implements service-to-service bearer token authentication for ATOS `/api/studio`.

Future options:

- HMAC signature over body and timestamp for push requests.
- Shared human login should only be considered after ATOS has a confirmed formal login/session/JWT boundary.

## Error Semantics

Suggested status codes:

- `201 Created`: new item created.
- `200 OK`: duplicate/upsert returned existing item.
- `400 Bad Request`: malformed JSON or missing required fields.
- `401 Unauthorized`: invalid future service token.
- `409 Conflict`: incompatible state or protocol version.
- `422 Unprocessable Entity`: validation failed.
- `503 Service Unavailable`: Studio storage unavailable.
