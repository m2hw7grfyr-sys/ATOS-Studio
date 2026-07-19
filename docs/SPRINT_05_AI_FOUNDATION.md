# Studio Sprint 05 AI Foundation

## Goal

Sprint 05 establishes the AI foundation for ATOS Studio:

```text
Topic Package
  -> AI Job
  -> LLM Provider
  -> AI Analysis
  -> GPT Director Prompt
  -> Editorial Brief Draft
```

This sprint does not implement video generation or automatic full script creation.

## Architecture

```text
Studio AI Service
  -> LLM Provider Interface
      -> Local Provider
          -> Ollama / vLLM compatible API
      -> OpenAI Provider
          -> OpenAI API
```

Rules:

- Business code calls `AIService`.
- Business code must not directly call Ollama, vLLM, or OpenAI.
- Local provider is the default.
- OpenAI is optional and disabled by default.
- Provider errors are stored on AI jobs and do not crash Studio.

## Configuration

```env
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
OPENAI_TIMEOUT_SECONDS=120
```

API keys must not be committed, returned to the frontend, or written to logs.

## Database

Migration:

```text
0004_add_ai_framework
```

New tables:

- `studio_prompt_templates`
- `studio_ai_jobs`
- `studio_ai_analyses`
- `studio_editorial_briefs`

## Prompt Templates

Default prompt templates:

- 内容摘要模板, category `analysis`
- 用户痛点分析模板, category `audience`
- 评论洞察模板, category `comments`
- 视频方向分析模板, category `video_angle`

Prompt APIs:

```text
GET  /api/prompt-templates
POST /api/prompt-templates
```

Disabled templates are not selected by AI jobs.

## AI Jobs

Table:

```text
studio_ai_jobs
```

Statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

Job types:

- `topic_summary`
- `pain_point_analysis`
- `comment_analysis`
- `video_angle_analysis`

APIs:

```text
GET  /api/ai/health
POST /api/topic-packages/{topic_package_id}/ai-jobs
GET  /api/topic-packages/{topic_package_id}/ai-jobs
POST /api/ai/jobs/{job_id}/run
GET  /api/topic-packages/{topic_package_id}/ai-analyses
```

## AI Analysis

Table:

```text
studio_ai_analyses
```

Analysis types:

- `summary`
- `pain_points`
- `comments`
- `video_angle`

Each record stores:

- Provider
- Model
- Prompt version
- Result JSON
- Timestamp

## Topic Package UI

Topic package detail now includes:

- `AI分析` button
- AI job list
- AI job run action
- AI Insights result table
- Link to GPT Director

The `AI分析` button creates pending jobs. It does not automatically create video scripts.

## GPT Director

Page:

```text
/gpt-director
```

The page displays:

- Topic package title
- Topic package summary
- AI analysis results
- Copyable GPT prompt
- JSON receiving area
- Saved Editorial Brief drafts

Editorial Brief API:

```text
POST /api/editorial-briefs
```

Editorial Brief statuses:

- `draft`
- `reviewed`
- `approved`

Sprint 05 only saves drafts.

## Operator Manual

Manual path:

```text
docs/operator-manual/ATOS_STUDIO_OPERATOR_MANUAL.md
```

The manual covers:

- System introduction
- Current workflow
- Page descriptions
- Button descriptions
- AI behavior

Future sprints must update the operator manual when pages, buttons, or workflows change.

## Tests

Run:

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover tests
```

Covered:

- AI health when providers are unconfigured or unavailable
- Prompt template creation and listing
- AI job creation
- Successful AI job execution with fake provider
- Failed AI job execution with stored error
- AI analysis persistence
- GPT Director page
- Editorial Brief draft save
- Existing content pool and topic package workflows
- Empty database migration

## Not Implemented

- Video generation
- ComfyUI
- Wan
- FLUX
- CogVideoX
- Kling
- Runway
- Veo
- TTS
- Subtitles
- FFmpeg
- Automatic publish
- Automatic GPT full script generation
