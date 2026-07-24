from __future__ import annotations


class GenerationStep:
    PREPARE = "prepare"
    SCENE_GENERATION = "scene_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    VOICEOVER = "voiceover"
    SUBTITLES = "subtitles"
    COMPOSITION = "composition"
    ARCHIVE = "archive"


IMAGE_GENERATION_FLOW = [
    GenerationStep.PREPARE,
    GenerationStep.IMAGE_GENERATION,
    GenerationStep.ARCHIVE,
]


GENERATION_TASK_STATUSES = {
    "pending",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "paused",
}
