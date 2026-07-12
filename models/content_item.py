from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StudioContentItem(Base):
    __tablename__ = "studio_content_items"
    __table_args__ = (
        UniqueConstraint("source_platform", "source_post_id", name="uq_studio_content_source_post"),
        UniqueConstraint("source_hash", name="uq_studio_content_source_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_platform: Mapped[str] = mapped_column(String(80), index=True)
    atos_post_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    source_post_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[Optional[str]] = mapped_column(String(200))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    source_score: Mapped[Optional[int]] = mapped_column()
    comment_count: Mapped[Optional[int]] = mapped_column()
    risk_level: Mapped[Optional[str]] = mapped_column(String(40))
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    source_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending_review", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="manual_import", index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

