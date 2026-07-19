# Sprint 09: Generation Queue Framework

Status: Implemented

## Sprint Goal

Build the Generation Queue Layer for ATOS Studio 1.0.

This sprint creates production planning infrastructure only. It does not connect ComfyUI, FLUX, Wan, CogVideoX, TTS, FFmpeg, Kling, Runway, Veo, or any publishing service.

## Completed

- Video Project supports `general` and `persona` creation modes.
- `persona_id` and `social_account_id` are nullable for general production planning.
- Seed migration adds `Default Creator`.
- Added `studio_generation_pipelines`.
- Expanded `studio_generation_tasks` with priority, retry, dependency, provider, schedule, and context fields.
- Added `GenerationPlanner`.
- Added provider adapter framework under `services/generation/providers/`.
- Added provider registry for `comfyui`, `flux`, `wan`, `tts`, `ffmpeg`, `kling`, `runway`, and `veo`.
- Added Generation Queue page.
- Added Video Project generation pipeline section and `创建生成计划` action.
- Updated operator manual.

## Flow

```text
Editorial Brief
↓
Video Project
↓
Create Generation Plan
↓
Generation Pipeline
↓
Generation Tasks
↓
Generation Queue
```

## Task Split

For each scene:

- `image_generation`
- `video_generation`

For the full project:

- `voice_generation`
- `subtitle_generation`
- `composition`

## Context

Every task stores:

```json
{
  "topic_package_id": "",
  "editorial_brief_id": "",
  "video_project_id": "",
  "persona_id": "",
  "social_account_id": "",
  "scene_id": ""
}
```

## Provider Adapter Contract

All future generation providers must implement:

- `generate()`
- `health_check()`
- `get_status()`
- `cancel()`

Current adapters are placeholders and return `not_configured`.

## Known Limitations

- No real generation execution.
- No provider authentication.
- No media file outputs.
- No task worker.
- Multiple generation plans can be created for the same project; this is intentional for versioned planning.

## Validation

Covered by tests:

- General mode Video Project creation.
- Persona mode compatibility.
- Generation Pipeline creation.
- Generation Task split.
- Provider Registry health.
- Generation Queue page rendering.
