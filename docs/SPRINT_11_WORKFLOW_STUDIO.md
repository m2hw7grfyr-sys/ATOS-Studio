# Sprint 11: Workflow Studio And Model Capability Registry

Status: Implemented

## Goal

Build the ComfyUI Workflow Studio and Model Capability Registry.

Operators can import workflows, validate workflow JSON, test workflows, mark successful workflows as available, and bind workflows to required model capabilities.

## In Scope

- ComfyUI image-generation workflows.
- Workflow import and validation.
- Workflow test result storage.
- Model capability registry.
- Generation preflight checks.
- Workflow selection before Scene image generation.

## Out Of Scope

- Wan.
- Video generation.
- TTS.
- FFmpeg.
- Auto publishing.
- Automatic model selection.
- Model training.

## Workflow Lifecycle

```text
draft
↓
testing
↓
available
```

Failed tests keep the workflow in `draft` and store the error in `test_result_json`.

## Preflight

Before execution, the Generation Executor checks:

1. Workflow exists and is `available`.
2. Provider health is available.
3. Required models exist with status `available`.

Failure reasons:

- `workflow_not_available`
- `provider_offline`
- `missing_model`

## Model Capability

Model capability records include:

- name
- provider
- model_type
- version
- status
- metadata

Supported status values:

- available
- missing
- disabled

## Pages

- `/workflows`: Workflow Studio and Model Capability Registry.
- `/video-projects/{id}`: Scene image generation requires selecting an available Workflow.
- `/generation-queue`: shows Provider Task ID, Asset status, and error reason.

## Validation

Covered by tests:

- Invalid Workflow JSON.
- Workflow import.
- Workflow test success.
- Model capability creation.
- Missing model preflight failure.
- Workflow page rendering.
- ComfyUI disabled/unavailable health checks.
