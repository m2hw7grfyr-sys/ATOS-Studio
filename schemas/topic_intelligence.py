from __future__ import annotations

import json
from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    BaseModel = object  # type: ignore
    Field = lambda default_factory=None, default=None: default if default_factory is None else default_factory()  # type: ignore


class AudienceInsight(BaseModel):
    persona: str = ""
    needs: list[str] = Field(default_factory=list)


class PainPointInsight(BaseModel):
    problem: str = ""
    frequency: str = ""
    emotion: str = ""


class UserQuoteInsight(BaseModel):
    quote: str = ""
    source: str = ""
    engagement: int = 0


class ContentOpportunityInsight(BaseModel):
    angle: str = ""
    reason: str = ""
    recommended_format: str = ""


class VideoDirectionInsight(BaseModel):
    recommended_hook: str = ""
    recommended_style: str = ""
    target_platforms: list[str] = Field(default_factory=list)


class OpportunityScore(BaseModel):
    total: int = 0
    engagement: int = 0
    comment_quality: int = 0
    emotion: int = 0
    commercial: int = 0


class TopicIntelligenceResult(BaseModel):
    core_summary: str = ""
    audience: AudienceInsight = Field(default_factory=AudienceInsight)
    pain_points: list[PainPointInsight] = Field(default_factory=list)
    emotional_triggers: list[str] = Field(default_factory=list)
    controversies: list[str] = Field(default_factory=list)
    user_quotes: list[UserQuoteInsight] = Field(default_factory=list)
    content_opportunities: list[ContentOpportunityInsight] = Field(default_factory=list)
    video_direction: VideoDirectionInsight = Field(default_factory=VideoDirectionInsight)
    opportunity_score: OpportunityScore = Field(default_factory=OpportunityScore)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def parse_topic_intelligence_json(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("topic intelligence output must be a JSON object")
    result = TopicIntelligenceResult(**value)
    return model_to_dict(result)
