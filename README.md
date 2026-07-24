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

Sprint 05 adds the AI foundation:

```text
studio_topic_packages -> AI jobs -> AI analyses -> GPT director prompt -> editorial brief draft
```

Sprint 06 adds topic intelligence:

```text
topic package -> package-level AI context -> topic_intelligence_analysis -> structured strategy insights
```

Video generation, Wan, TTS, subtitles, FFmpeg, cloud backup, automatic ingestion, clustering, and shared user login are not implemented. ComfyUI image generation is supported when `COMFYUI_URL` is configured.

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
AI_PROVIDER=local
AI_DEFAULT_MODEL=qwen3
AI_TIMEOUT_SECONDS=120
AI_MAX_TOKENS=1200
AI_TEMPERATURE=0.3
AI_OUTPUT_FORMAT=json
LOCAL_LLM_TYPE=ollama
LOCAL_LLM_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen3
LOCAL_LLM_TIMEOUT_SECONDS=120
OPENAI_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=
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
http://127.0.0.1:8502/gpt-director
```

## AI Foundation

Studio AI uses a provider interface. Business code calls the Studio AI Service, not Ollama, vLLM, or OpenAI directly.

Provider strategy:

1. Local provider first, default.
2. OpenAI provider optional and disabled by default.

Health:

```bash
curl http://127.0.0.1:8502/api/ai/health
```

Prompt templates:

```text
GET  /api/prompt-templates
POST /api/prompt-templates
```

AI jobs:

```text
POST /api/topic-packages/{topic_package_id}/ai-jobs
POST /api/ai/jobs/{job_id}/run
GET  /api/topic-packages/{topic_package_id}/ai-analyses
```

Default job types:

- `topic_summary`
- `pain_point_analysis`
- `comment_analysis`
- `video_angle_analysis`
- `topic_intelligence_analysis`

OpenAI API keys are never returned by API responses and must not be committed.

## Topic Intelligence

Topic Intelligence analyzes a full topic package rather than a single content item. The context includes package metadata, all active source items, optional comments, and optional engagement metrics.

Supported source fields:

- `title`
- `body`
- `source_platform`
- `source_url`
- `author`
- `created_at`
- `score`
- `upvotes`
- `likes`
- `comments_count`
- `views`
- `reposts`
- `bookmarks`

Missing comments or metrics are allowed and are passed as empty lists or null values. Studio does not fabricate metrics.

Create and run a topic intelligence job:

```bash
curl -X POST "http://127.0.0.1:8502/api/topic-packages/{topic_package_id}/ai-jobs?job_type=topic_intelligence_analysis"
curl -X POST "http://127.0.0.1:8502/api/ai/jobs/{job_id}/run"
```

Open the topic package detail page and use:

- `生成主题智能分析`
- `重新分析`
- `执行`

Each run creates a new `studio_ai_analyses` row with `analysis_type=topic_intelligence`. Old versions are retained and shown as `Analysis Version 1`, `Analysis Version 2`, and so on.

Structured result fields:

- `core_summary`
- `audience`
- `pain_points`
- `emotional_triggers`
- `controversies`
- `user_quotes`
- `content_opportunities`
- `video_direction`
- `opportunity_score`

## GPT Director

The GPT director page is now the Editorial Studio. It prepares a copyable prompt from:

- Topic package title
- Topic package sources
- AI analyses
- Latest topic intelligence result

It also stores manually pasted GPT Output JSON as versioned Editorial Briefs.

Sprint 07 does not call GPT APIs and does not generate video. The operator manually copies the generated prompt into ChatGPT, then pastes the returned JSON back into Studio.

Sprint 08 adds the production management layer:

```text
Editorial Brief -> Persona -> Social Account -> Video Project -> Scenes -> future generation tasks
```

It does not connect ComfyUI, video models, TTS, FFmpeg, or automatic publishing.

Open:

```text
http://127.0.0.1:8502/gpt-director
```

Prompt builder:

```bash
curl "http://127.0.0.1:8502/api/topic-packages/{topic_package_id}/editorial-prompt"
```

Save GPT Output JSON:

```bash
curl -X POST http://127.0.0.1:8502/api/editorial-briefs \
  -H "Content-Type: application/json" \
  -d '{"topic_package_id":"uuid","prompt_snapshot":"prompt text","output_json":{"title":"...","hook":"...","script":"...","scenes":[{"scene_number":1,"duration":5,"visual_prompt":"...","voiceover":"...","subtitle":"..."}],"caption":"...","hashtags":[]}}'
```

Required GPT Output JSON fields:

- `title`
- `hook`
- `script`
- `scenes`
- `caption`

Each scene requires:

- `scene_number`
- `duration`
- `visual_prompt`
- `voiceover`
- `subtitle`

Each save creates a new version. Old versions are retained and visible in the Editorial Studio page.

## Persona And Video Projects

Personas define the publishing identity and style used by Editorial Studio prompts.

Open:

```text
http://127.0.0.1:8502/accounts
```

Persona fields include:

- name
- description
- target_audience
- persona_profile JSON
- tone_style
- language_style
- visual_style
- voice_style
- content_rules JSON

Social accounts bind a real publishing account to one Persona:

- platform
- username
- display_name
- persona_id
- status
- publishing_rules JSON

The default seeded persona/account is:

- Persona: `Brainy（小脑瓜）`
- Account: TikTok `@TiredBrainClub`
- Positioning: late-night ADHD, overthinking, anxiety, procrastination, high-sensitivity, and soft self-acceptance content.

Generate an Editorial Prompt for a specific Persona:

```bash
curl "http://127.0.0.1:8502/api/topic-packages/{topic_package_id}/editorial-prompt?persona_id={persona_id}"
```

Create a Video Project from an Editorial Brief:

```bash
curl -X POST http://127.0.0.1:8502/api/video-projects/from-brief \
  -H "Content-Type: application/json" \
  -d '{"editorial_brief_id":"brief-uuid","persona_id":"persona-uuid","social_account_id":"account-uuid"}'
```

Open:

```text
http://127.0.0.1:8502/video-projects
```

Video Projects initialize scenes from the Editorial Brief `scenes` JSON. Sprint 09 adds a Generation Queue planning layer. It creates pipeline and task records only; it does not call ComfyUI, FLUX, Wan, TTS, FFmpeg, Kling, Runway, Veo, or any other generation provider.

### Persona Mode And General Mode

Video Projects support two creation modes:

- `general`: no Persona or Social Account is required. Use this for generic production planning.
- `persona`: requires a Persona and may bind a Social Account filtered by that Persona.

The migration seeds a system Persona named `Default Creator`, but general mode keeps `persona_id` empty by design.

### Create A Generation Plan

From the Video Project detail page, click `创建生成计划`.

API:

```bash
curl -X POST http://127.0.0.1:8502/api/video-projects/{video_project_id}/generation-plan
```

The planner creates:

- per-scene `image_generation`
- per-scene `video_generation`
- whole-project `voice_generation`
- whole-project `subtitle_generation`
- whole-project `composition`

Each task stores `context_json` with:

- `topic_package_id`
- `editorial_brief_id`
- `video_project_id`
- `persona_id`
- `social_account_id`
- `scene_id`

Open:

```text
http://127.0.0.1:8502/generation-queue
```

Provider adapters live under `services/generation/providers/`. Sprint 09 only registers placeholder adapters and health checks.

## ComfyUI Image Generation

Sprint 10 adds the first real generation adapter: ComfyUI image generation.

Environment:

```bash
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_TIMEOUT_SECONDS=120
```

If `COMFYUI_URL` is empty, the Video Project page shows `ComfyUI 未配置。`. Studio starts normally when ComfyUI is unavailable.

Health:

```bash
curl http://127.0.0.1:8502/api/generation/providers/comfyui/health
```

Workflow:

```bash
curl "http://127.0.0.1:8502/api/generation-workflows?provider=comfyui&workflow_type=image_generation"
```

Generate an image for a scene. Studio uses the first `available` `image_generation` workflow:

```bash
curl -X POST "http://127.0.0.1:8502/api/scenes/{scene_id}/generate-image?run_now=true"
```

Run an existing image task:

```bash
curl -X POST http://127.0.0.1:8502/api/generation-tasks/{task_id}/run
```

All generated results are saved as Studio Assets in `studio_assets`. The Video Project page shows scene image status and preview. The Generation Queue shows Provider Task ID and Asset status.

Current limits:

- Only `image_generation` is executable.
- Video generation, TTS, subtitles, FFmpeg, publishing, Kling, Runway, and Veo are not implemented.
- The default workflow is a placeholder. Replace `studio_generation_workflows.workflow_json` with a real ComfyUI API workflow before production use.

## Workflow Studio And Model Capability Registry

Sprint 11 adds a Workflow Studio page:

```text
http://127.0.0.1:8502/workflows
```

Workflow APIs:

```bash
curl -X POST http://127.0.0.1:8502/api/generation-workflows \
  -H "Content-Type: application/json" \
  -d '{"name":"FLUX image workflow","provider":"comfyui","workflow_type":"image_generation","workflow_json":{"prompt":{"1":{"inputs":{"text":"{{visual_prompt}}"}}}}}'

curl -X POST http://127.0.0.1:8502/api/generation-workflows/{workflow_id}/test \
  -H "Content-Type: application/json" \
  -d '{"visual_prompt":"A simple test image"}'
```

Model Capability APIs:

```bash
curl -X POST http://127.0.0.1:8502/api/model-capabilities \
  -H "Content-Type: application/json" \
  -d '{"name":"FLUX.1 Schnell","provider":"comfyui","model_type":"image","status":"available"}'
```

Workflow lifecycle:

```text
draft -> testing -> available
```

Generation preflight checks:

- Provider health
- Workflow status is `available`
- Required models are registered as `available`

If a check fails, the Generation Task is marked `failed` and the queue shows the reason, such as `provider_offline`, `workflow_not_available`, or `missing_model`.

## Local Generation Engine Registry And Preflight

Sprint 16 adds a local generation engine registry so Studio does not hard-code model names, workflow IDs, or runtime clients inside task execution code.

Open the Generation Settings page:

```text
http://127.0.0.1:8502/generation-settings
```

The page shows:

- Engine status: ComfyUI, FLUX, Wan, Local TTS, FFmpeg, and reserved cloud adapters.
- Model profiles: engine, capability, enabled/default flags, estimated VRAM, and status.
- Generation presets: business-facing presets such as `image_scene_default`, linked to a model profile and workflow profile.

New Sprint 16 APIs:

```bash
curl http://127.0.0.1:8502/api/studio/generation/engines
curl "http://127.0.0.1:8502/api/studio/generation/engines?capability=image"
curl http://127.0.0.1:8502/api/studio/generation/models
curl http://127.0.0.1:8502/api/studio/generation/presets
curl -X POST http://127.0.0.1:8502/api/studio/generation/preflight \
  -H "Content-Type: application/json" \
  -d '{"project_id":"...","scene_id":"...","task_type":"image_generation","preset_id":"...","parameters":{"width":768,"height":1024}}'
curl http://127.0.0.1:8502/api/studio/jobs/{job_id}/generation-config
```

Configuration priority:

```text
task preset / task parameters
-> project or scene configuration
-> Studio default preset
-> system defaults
```

When a task starts generation, Studio stores a configuration snapshot containing:

- `engine_id`
- `model_profile_id`
- `workflow_profile_id`
- `preset_id`
- resolved parameters
- configuration version
- fallback metadata

This means changing a default preset later will not change an already-created or already-running task. Sprint 14 retry keeps the original snapshot. Use `retry-with-config` only when you intentionally want a failed task to use a new preset.

Preflight checks include:

- engine reachability, such as ComfyUI `/system_stats`
- workflow existence and JSON validity
- required model availability
- path traversal protection
- output and temp directory writability
- basic free disk space
- GPU/VRAM detection when available
- resolution, duration, and FPS support where configured

Common error codes:

```text
ENGINE_NOT_CONFIGURED
ENGINE_UNREACHABLE
MODEL_NOT_FOUND
WORKFLOW_NOT_FOUND
WORKFLOW_INVALID
FFMPEG_NOT_FOUND
OUTPUT_DIRECTORY_UNWRITABLE
INSUFFICIENT_DISK_SPACE
GPU_NOT_FOUND
INSUFFICIENT_VRAM
UNSUPPORTED_RESOLUTION
UNSUPPORTED_DURATION
UNSUPPORTED_FPS
INVALID_GENERATION_CONFIG
```

Fallback:

```env
STUDIO_ALLOW_PRESET_FALLBACK=false
```

Fallback is off by default. When enabled, Studio can evaluate lower-priority presets in the same capability and must record the selected fallback in the task snapshot. It never silently swaps an image task to a video model or changes configuration without storing the final resolved parameters.

Local path variables:

```env
STUDIO_MODEL_ROOT=storage/models
STUDIO_WORKFLOW_ROOT=storage/workflows
STUDIO_OUTPUT_ROOT=storage/outputs
STUDIO_TEMP_ROOT=storage/tmp
STUDIO_MIN_FREE_DISK_GB=1
FFMPEG_BINARY=ffmpeg
FFPROBE_BINARY=ffprobe
```

Do not put API keys, SSH credentials, database passwords, model files, generated images, or private absolute paths in Git.

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
