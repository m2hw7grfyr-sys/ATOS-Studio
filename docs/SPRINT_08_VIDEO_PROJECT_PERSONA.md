# Studio Sprint 08: Video Project + Persona System + Publishing Account Layer

Status: Completed

## Goal

Build the production management layer after Editorial Brief.

```text
Editorial Brief
↓
Persona
↓
Social Account
↓
Video Project
↓
Scenes
↓
Future Generation Tasks
```

## Non-goals

- No video model connection
- No ComfyUI
- No model download
- No TTS
- No FFmpeg
- No automatic publishing

## Persona System

Added `studio_personas`.

Stores:

- name
- description
- target_audience
- persona_profile_json
- tone_style
- language_style
- visual_style
- voice_style
- content_rules_json
- enabled

Persona JSON is intentionally flexible so new identity fields can be added without migrations.

## Social Account System

Added `studio_social_accounts`.

Stores:

- platform
- username
- display_name
- persona_id
- account_notes
- status
- publishing_rules_json

One Persona can bind many Social Accounts.

## Video Project Model

Added `studio_video_projects`.

Each Video Project binds:

- Topic Package
- Editorial Brief
- Persona
- optional Social Account

Statuses:

- draft
- planning
- ready_for_generation
- generating
- reviewing
- completed
- archived

## Scene Model

Added `studio_video_scenes`.

Scenes are initialized from Editorial Brief `scenes` JSON.

Fields:

- scene_number
- duration
- visual_prompt
- voiceover
- subtitle
- camera_direction
- status

## Generation Task Scaffold

Added `studio_generation_tasks`.

Task types:

- image_generation
- video_generation
- voice_generation
- subtitle_generation
- composition

No tasks are executed in Sprint 08.

## Prompt Persona Adaptation

`GPT Prompt Builder` now supports `persona_id`.

Prompt includes:

- Identity
- Tone
- Audience
- Language
- Style
- Voice
- Avoid rules

## UI

Added:

- `/accounts`
- `/video-projects`
- `/video-projects/{id}`

Updated:

- `/gpt-director` Persona selector
- Editorial Brief history now includes `创建视频项目`

## Tests

Covered:

- Persona create
- Persona edit
- Persona disable
- Social Account create
- Social Account Persona filter
- Persona included in Prompt
- Different Persona can alter Prompt context
- Video Project creation from Brief
- Scene initialization from Brief JSON
- Page rendering for accounts and video projects
- Alembic migration from empty SQLite database

