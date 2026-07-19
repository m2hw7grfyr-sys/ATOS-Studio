# Studio Sprint 04 Topic Packages

## Goal

Sprint 04 upgrades ATOS Studio from a content pool into a manual review and topic-package workspace.

Flow:

```text
Studio Content Pool
  -> Manual Review
  -> Topic Package
  -> Topic Package Approval
```

Topic packages are stable content input units for later GPT director and video-project workflows. They are not video projects and do not trigger generation.

## Database

Migration:

```text
0003_add_topic_packages
```

New tables:

- `studio_topic_packages`
- `studio_topic_package_items`
- `studio_audit_events`

Changed table:

- `studio_content_items`

Added fields:

- `review_note`
- `reviewed_at`
- `approved_at`
- `rejected_at`
- `archived_at`

## Topic Package Concept

A topic package represents a group of source posts around the same core problem, user pain, or content angle.

Example:

```text
Title: ADHD medication wears off too early
Sources:
- Reddit post A
- Reddit post B
- X post C
```

## Status

Content item and topic package statuses:

- `pending_review`
- `approved`
- `rejected`
- `archived`

Topic package priority:

- `low`
- `normal`
- `high`
- `urgent`

Risk level:

- `low`
- `medium`
- `high`
- `unknown`

## Content Pool Review

The content pool supports:

- Single approve, reject, archive
- Batch approve, reject, archive
- Restore to pending review
- Create topic package from selected content
- Review notes
- Review timestamps

Batch endpoint:

```text
POST /api/content-items/status-batch
```

Request:

```json
{
  "content_item_ids": ["uuid-1", "uuid-2"],
  "status": "approved",
  "review_note": "适合后续做短视频"
}
```

Rules:

- Max 100 IDs.
- Empty ID list returns validation error.
- Request IDs are deduplicated.
- Missing items are reported per item.
- One missing item does not fail the whole batch.

## Create Topic Package

Endpoint:

```text
POST /api/topic-packages/from-content-items
```

Request:

```json
{
  "title": "ADHD medication wears off too early",
  "content_item_ids": ["uuid-1", "uuid-2"],
  "summary": "",
  "content_angle": "解释型",
  "target_content_type": "video",
  "target_platforms": ["tiktok", "youtube_shorts"],
  "operator_note": ""
}
```

Rules:

- Requires at least one content item.
- Max 100 content items.
- Request IDs are deduplicated.
- Missing content items return validation error.
- First content item is primary by default unless `primary_content_item_id` is provided.
- Creating a topic package does not change content item review status.

## Member Management

Endpoints:

```text
POST   /api/topic-packages/{id}/items
DELETE /api/topic-packages/{id}/items/{content_item_id}
PATCH  /api/topic-packages/{id}/primary-item
PATCH  /api/topic-packages/{id}/items/order
```

Rules:

- Same content item cannot be active twice in one topic package.
- Same content item can belong to multiple topic packages.
- Removing a source sets `removed_at`.
- If the removed source was primary, the next active source becomes primary.
- Empty topic packages are allowed and shown as a warning on the detail page.
- Ordering must include exactly all active members.

## Statistics

The service recalculates:

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

The frontend never calculates these values.

## Similar Topic Hints

Endpoint:

```text
GET /api/topic-packages/similar?title=...
```

Implementation:

- Normalize title.
- Compare title token overlap.
- Return possible duplicates only.

Not implemented:

- Embedding API
- Vector database
- LLM clustering
- Automatic merge

## Manual Merge

Endpoint:

```text
POST /api/topic-packages/merge
```

Request:

```json
{
  "target_topic_package_id": "uuid-target",
  "source_topic_package_ids": ["uuid-source"],
  "archive_sources": true
}
```

Rules:

- Active source items from source packages are added to the target.
- Duplicate source items are skipped.
- Target package title and review status are preserved.
- Source packages are archived by default.
- Source package `merged_into_topic_package_id` points to the target.
- No package is physically deleted.

## Audit Events

Table:

```text
studio_audit_events
```

Recorded actions:

- Content item status changes
- Topic package creation
- Topic package update
- Topic package status change
- Add source
- Remove source
- Set primary source
- Sort sources
- Merge topic packages

Audit events do not store tokens, cookies, database credentials, or Authorization headers.

## Pages

Content Pool:

```text
/content-pool
```

Topic Packages:

```text
/topic-packages
/topic-packages/{topic_package_id}
```

Topic package detail includes:

- Basic info
- Aggregated statistics
- Source content list
- Similar topic hints
- Manual merge
- Audit history

## Migration

```bash
cd /Users/zhangkaikai/Documents/INDEX/ATOS-Studio
.venv/bin/alembic upgrade head
```

## Tests

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover tests
```

Covered:

- Empty database migration
- Sprint 03 SQLite upgrade
- Single status update
- Batch status update
- Partial batch failure
- Topic package creation from one or multiple items
- Request ID deduplication
- Duplicate add
- Restore removed source
- Remove source
- Primary source uniqueness
- Sorting
- Statistics recalculation
- Risk aggregation
- Status change
- Soft archive
- Similar topic hints
- Manual merge
- Audit events
- Topic package list/detail pages

## Troubleshooting

`no such column: studio_content_items.review_note`

Run:

```bash
.venv/bin/alembic upgrade head
```

`topic package item not found`

The source may already have been removed or does not belong to the package.

`ordered_content_item_ids must exactly match active members`

The order request must include every active source exactly once.

## Not Implemented

- Automatic topic clustering
- Vector database
- Embedding API
- GPT director exchange
- Video projects
- ComfyUI
- Wan
- FLUX
- Voiceover
- Subtitles
- FFmpeg
- Automatic publishing
- Formal user login
