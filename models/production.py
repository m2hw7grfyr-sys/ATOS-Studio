from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.content_item import new_uuid, utc_now


class StudioPersona(Base):
    __tablename__ = "studio_personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(String(500), default="")
    persona_profile_json: Mapped[str] = mapped_column(Text, default="{}")
    tone_style: Mapped[str] = mapped_column(String(200), default="")
    language_style: Mapped[str] = mapped_column(String(200), default="")
    visual_style: Mapped[str] = mapped_column(String(500), default="")
    voice_style: Mapped[str] = mapped_column(String(500), default="")
    content_rules_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioSocialAccount(Base):
    __tablename__ = "studio_social_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    platform: Mapped[str] = mapped_column(String(80), index=True)
    username: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    persona_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("studio_personas.id"), index=True)
    account_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="testing", index=True)
    publishing_rules_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioVideoProject(Base):
    __tablename__ = "studio_video_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    topic_package_id: Mapped[str] = mapped_column(String(36), ForeignKey("studio_topic_packages.id"), index=True)
    editorial_brief_id: Mapped[str] = mapped_column(String(36), ForeignKey("studio_editorial_briefs.id"), index=True)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("studio_personas.id"), index=True)
    social_account_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("studio_social_accounts.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(60), default="draft", index=True)
    target_platforms_json: Mapped[str] = mapped_column(Text, default="[]")
    aspect_ratio: Mapped[str] = mapped_column(String(40), default="9:16")
    duration_target: Mapped[Optional[int]] = mapped_column()
    priority: Mapped[str] = mapped_column(String(40), default="normal", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioVideoScene(Base):
    __tablename__ = "studio_video_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("studio_video_projects.id"), index=True)
    scene_number: Mapped[int] = mapped_column(default=1, index=True)
    duration: Mapped[Optional[float]] = mapped_column()
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    voiceover: Mapped[str] = mapped_column(Text, default="")
    subtitle: Mapped[str] = mapped_column(Text, default="")
    camera_direction: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioGenerationTask(Base):
    __tablename__ = "studio_generation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    video_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("studio_video_projects.id"), index=True)
    scene_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("studio_video_scenes.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
