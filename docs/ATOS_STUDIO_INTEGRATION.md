# ATOS Studio Integration Protocol

Sprint: Studio Sprint 01
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
- Sprint 01 does not implement automatic ingestion.
- Missing optional generation services, including GPU Worker and ComfyUI, must not prevent Studio startup.

## Recommended Mode

Use ATOS internal APIs for ATOS-owned content and let Studio own future `studio_` data.

Direct shared database access is not recommended for ATOS core tables because it would couple two release cycles and allow Studio to bypass ATOS lifecycle rules. A future mixed deployment may place `studio_` tables in the same database instance, but those tables must remain Studio-owned.

## Suggested API Contract

The following API names define the future protocol. They are not fully implemented in Sprint 01.

### Create Or Upsert Content Item

`POST /api/studio/content-items`

Suggested request:

```json
{
  "source_platform": "reddit",
  "source_post_id": "external-or-internal-id",
  "atos_post_id": "atos-post-uuid-or-id",
  "source_url": "https://example.com/post",
  "title": "post title",
  "body": "post body",
  "author": "author",
  "published_at": "2026-07-12T00:00:00Z",
  "score": 0,
  "comment_count": 0,
  "risk_level": "low",
  "tags": [],
  "metadata": {}
}
```

Suggested successful response:

```json
{
  "id": "studio-content-item-id",
  "status": "created",
  "idempotency_key": "reddit:external-or-internal-id"
}
```

Suggested duplicate response:

```json
{
  "id": "existing-studio-content-item-id",
  "status": "duplicate",
  "idempotency_key": "reddit:external-or-internal-id"
}
```

### List Content Items

`GET /api/studio/content-items`

Suggested query parameters:

- `source_platform`
- `status`
- `tag`
- `created_after`
- `limit`
- `cursor`

### Get Content Item

`GET /api/studio/content-items/{id}`

Returns one Studio content item and references back to ATOS source IDs.

### Get Project Status

`GET /api/studio/projects/{id}/status`

Suggested response:

```json
{
  "id": "studio-project-id",
  "status": "draft",
  "source_content_item_id": "studio-content-item-id",
  "generation_queue_status": "not_started",
  "updated_at": "2026-07-12T00:00:00Z"
}
```

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
- If the new payload contains additional non-empty fields, a future sprint may merge metadata, but Sprint 01 only defines the behavior.

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

## Future Authentication

Sprint 01 does not implement API authentication.

Recommended future options:

- Service-to-service bearer token stored in `.env`, for example `ATOS_STUDIO_API_TOKEN`.
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

