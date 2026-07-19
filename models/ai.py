from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.content_item import new_uuid, utc_now


class StudioPromptTemplate(Base):
    __tablename__ = "studio_prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    template: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioAIJob(Base):
    __tablename__ = "studio_ai_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(80))
    model: Mapped[Optional[str]] = mapped_column(String(120))
    input_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class StudioAIAnalysis(Base):
    __tablename__ = "studio_ai_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    topic_package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("studio_topic_packages.id"),
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(String(80), index=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioEditorialBrief(Base):
    __tablename__ = "studio_editorial_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    topic_package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("studio_topic_packages.id"),
        index=True,
    )
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    prompt_snapshot: Mapped[str] = mapped_column(Text, default="")
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
