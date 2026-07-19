# Studio Sprint 07: Editorial Studio

Status: Completed

## Goal

Build the GPT editorial exchange area that converts Topic Intelligence into a copyable GPT prompt and stores manually pasted GPT JSON as versioned Editorial Briefs.

## Non-goals

- No automatic OpenAI API calls
- No video generation
- No ComfyUI
- No video model integration
- No automatic publishing

## Architecture

```text
Topic Package
↓
Topic Intelligence Result
↓
GPT Prompt Builder
↓
Manual ChatGPT Exchange
↓
GPT Output JSON
↓
Schema Validation
↓
Versioned Editorial Brief
```

## Editorial Brief

`studio_editorial_briefs` now stores:

- topic_package_id
- version
- status
- prompt_template_id
- prompt_snapshot
- input_context_json
- output_json
- created_by
- created_at
- updated_at

The previous `input_json` field is retained for compatibility. New writes store the validated output in both `output_json` and `input_json`.

## Status

Implemented:

- draft
- reviewing
- approved

Reserved:

- archived
- ready_for_video

## Prompt Builder

`services/gpt_prompt_builder.py` builds prompts from:

- Topic Package
- Latest `topic_intelligence` analysis
- Editorial prompt template

It does not call GPT APIs.

## Prompt Template

Migration `0006_upgrade_editorial_briefs.py` adds:

- category: `editorial`
- name: `Short Video Script Template`
- target: TikTok, Reels, YouTube Shorts

## JSON Schema

`schemas/editorial_brief.py` validates:

- title
- hook
- script
- scenes
- caption

Each scene requires:

- scene_number
- duration
- visual_prompt
- voiceover
- subtitle

Optional:

- camera_direction
- target_audience
- hashtags

## Versioning

Each GPT Output save creates a new row:

- Version 1
- Version 2
- Version 3

Old versions are not overwritten.

## UI

`/gpt-director` now includes:

- Material context
- Prompt generation
- Copy Prompt button
- GPT Output JSON input
- Parse and save action
- Editorial Brief history
- Status update actions

## Tests

Covered:

- Prompt generation
- Missing Topic Intelligence error
- Missing editorial template error through the prompt builder boundary
- Valid GPT JSON
- Non-JSON error
- Missing field error
- Empty scenes error
- Version 1 and Version 2 creation
- Status update
- Editorial Studio page rendering

