# Studio Sprint 06: Topic Intelligence Engine

Status: Completed

## Goal

Build a Topic Intelligence Engine that analyzes a full Topic Package rather than individual content items.

## Scope

Implemented:

- Topic package level AI context builder
- Structured Topic Intelligence schema
- `topic_intelligence_analysis` AI job type
- `topic_intelligence` analysis type
- Default Topic Intelligence prompt template
- Topic package detail UI for generating, rerunning, and viewing versions
- Compatibility layer for optional comments and engagement metrics
- Operator manual update

Not implemented:

- Video generation
- ComfyUI
- Wan / FLUX / CogVideoX / Kling / Runway / Veo
- TTS
- FFmpeg
- Automatic publishing
- Automatic topic package creation
- Direct OpenAI API calls

## Architecture

```text
Topic Package
↓
TopicIntelligenceService
↓
AI context builder
↓
Studio AI Service provider boundary
↓
JSON schema validation
↓
studio_ai_analyses.result_json
↓
Topic package detail UI
```

## Input Data

Each content item contributes:

- title
- body
- source_platform
- source_url
- author
- created_at
- published_at
- metrics
- comments

Metrics are read from Studio fields and optional metadata/source snapshot keys:

- score
- upvotes
- likes
- comments_count
- views
- reposts
- bookmarks

Missing fields remain `null`; Studio does not fabricate engagement metrics.

## Comments

Comments are read from compatible metadata/source snapshot keys:

- comments
- raw_comments
- comments_json
- top_comments
- comment_items

If comments are missing, the context uses an empty list.

## Output Schema

The stored result is validated as:

- core_summary
- audience
- pain_points
- emotional_triggers
- controversies
- user_quotes
- content_opportunities
- video_direction
- opportunity_score

Invalid JSON marks the AI job as `failed` and stores the error message.

## UI

Topic package detail now includes:

- Generate Topic Intelligence button
- Reanalyze button
- Job status table
- Structured topic intelligence result
- Version history
- Raw AI result table

## User Quotes

Sprint 06 stores high-value user quotes inside `studio_ai_analyses.result_json`.

A dedicated `studio_user_quotes` table is intentionally deferred until quote curation becomes a separate workflow.

## Tests

Covered:

- Topic package with multiple posts
- Topic package with comments
- Missing comments
- Missing metrics
- AI job creation
- AI job success
- AI job failure on invalid JSON
- Schema default handling
- UI buttons and version history

