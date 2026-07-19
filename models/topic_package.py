from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.content_item import new_uuid, utc_now


class StudioTopicPackage(Base):
    __tablename__ = "studio_topic_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(300), index=True)
    normalized_title: Mapped[str] = mapped_column(String(300), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    content_angle: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="pending_review", index=True)
    risk_level: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    priority: Mapped[str] = mapped_column(String(40), default="normal", index=True)
    source_count: Mapped[int] = mapped_column(default=0)
    total_comment_count: Mapped[int] = mapped_column(default=0)
    average_source_score: Mapped[Optional[float]] = mapped_column()
    max_source_score: Mapped[Optional[int]] = mapped_column()
    target_content_type: Mapped[Optional[str]] = mapped_column(String(60))
    target_platforms_json: Mapped[str] = mapped_column(Text, default="[]")
    operator_note: Mapped[Optional[str]] = mapped_column(String(2000))
    created_by: Mapped[Optional[str]] = mapped_column(String(120))
    merged_into_topic_package_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioTopicPackageItem(Base):
    __tablename__ = "studio_topic_package_items"
    __table_args__ = (
        UniqueConstraint("topic_package_id", "content_item_id", name="uq_topic_package_content_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    topic_package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("studio_topic_packages.id"),
        index=True,
    )
    content_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("studio_content_items.id"),
        index=True,
    )
    position: Mapped[int] = mapped_column(default=0)
    is_primary: Mapped[bool] = mapped_column(default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StudioAuditEvent(Base):
    __tablename__ = "studio_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
