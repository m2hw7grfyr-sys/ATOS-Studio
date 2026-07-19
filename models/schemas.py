from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


VALID_CONTENT_STATUSES = {"pending_review", "approved", "rejected", "archived"}
VALID_TOPIC_PACKAGE_STATUSES = {"pending_review", "approved", "rejected", "archived"}
VALID_TOPIC_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_RISK_LEVELS = {"low", "medium", "high", "unknown"}


class AtosContentItem(BaseModel):
    atos_post_id: str
    atos_post_uuid: Optional[str] = None
    source_platform: str
    source_post_id: Optional[str] = None
    source_url: Optional[str] = None
    title: str
    body: str = ""
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    score: Optional[int] = None
    comment_count: Optional[int] = None
    risk_level: Optional[str] = None
    tags: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudioPushContext(BaseModel):
    requested_content_type: Optional[str] = None
    target_platforms: list[str] = Field(default_factory=list)
    operator_note: str = Field(default="", max_length=500)


class StudioContentPushRequest(BaseModel):
    source_platform: str = Field(min_length=1, max_length=80)
    atos_post_id: Optional[str] = Field(default=None, max_length=80)
    source_post_id: Optional[str] = Field(default=None, max_length=200)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    title: Optional[str] = Field(default=None, max_length=500)
    body: str = ""
    author: Optional[str] = Field(default=None, max_length=200)
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    source_score: Optional[int] = None
    comment_count: Optional[int] = None
    risk_level: Optional[str] = Field(default=None, max_length=40)
    tags: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    push_context: StudioPushContext = Field(default_factory=StudioPushContext)

    def to_atos_content_item(self) -> AtosContentItem:
        title = (self.title or "").strip()
        body = self.body or ""
        if not self.atos_post_id and not self.source_post_id and not self.source_url:
            raise ValueError("atos_post_id, source_post_id, or source_url is required")
        if not title and not body.strip():
            raise ValueError("title or body is required")
        return AtosContentItem(
            atos_post_id=self.atos_post_id or "",
            source_platform=self.source_platform.lower(),
            source_post_id=self.source_post_id,
            source_url=self.source_url,
            title=title or body[:120] or "(Untitled)",
            body=body,
            author=self.author,
            published_at=self.published_at,
            collected_at=self.collected_at,
            score=self.source_score,
            comment_count=self.comment_count,
            risk_level=self.risk_level,
            tags=self.tags,
            metadata=self.metadata,
        )


class StudioContentPushResponse(BaseModel):
    created: bool
    duplicate: bool
    studio_item_id: str
    status: str
    source_type: str


class StudioSourceStatusItem(BaseModel):
    source_platform: str
    source_post_id: Optional[str] = None
    atos_post_id: Optional[str] = None


class StudioSourceStatusBatchRequest(BaseModel):
    items: list[StudioSourceStatusItem] = Field(min_length=1, max_length=200)


class StudioSourceStatusResponse(BaseModel):
    exists: bool
    studio_item_id: Optional[str] = None
    status: Optional[str] = None
    source_type: Optional[str] = None
    imported_at: Optional[datetime] = None
    last_pushed_at: Optional[datetime] = None


class AtosContentListResponse(BaseModel):
    items: list[AtosContentItem]
    total: int
    limit: int
    offset: int


class AtosHealthResponse(BaseModel):
    service: str
    status: str
    api_version: str


class ImportContentItemRequest(BaseModel):
    source_platform: str
    source_post_id: str


class StudioContentItemRead(BaseModel):
    id: str
    source_platform: str
    atos_post_id: Optional[str] = None
    source_post_id: Optional[str] = None
    source_url: Optional[str] = None
    title: str
    body: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    source_score: Optional[int] = None
    comment_count: Optional[int] = None
    risk_level: Optional[str] = None
    tags: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    source_hash: str
    status: str
    source_type: str
    requested_content_type: Optional[str] = None
    target_platforms: list[str] = Field(default_factory=list)
    operator_note: Optional[str] = None
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    last_pushed_at: Optional[datetime] = None
    push_count: int = 0
    imported_at: datetime
    created_at: datetime
    updated_at: datetime


class ContentItemListResponse(BaseModel):
    items: list[StudioContentItemRead]
    total: int
    limit: int
    offset: int


class ImportContentItemResponse(BaseModel):
    created: bool
    duplicate: bool
    item: StudioContentItemRead


class UpdateContentStatusRequest(BaseModel):
    status: str
    review_note: str = Field(default="", max_length=2000)


class ContentItemStatusBatchRequest(BaseModel):
    content_item_ids: list[str] = Field(min_length=1, max_length=100)
    status: str
    review_note: str = Field(default="", max_length=2000)


class TopicPackageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(default="", max_length=5000)
    content_angle: Optional[str] = Field(default=None, max_length=200)
    priority: str = "normal"
    target_content_type: Optional[str] = Field(default=None, max_length=60)
    target_platforms: list[str] = Field(default_factory=list, max_length=20)
    operator_note: Optional[str] = Field(default=None, max_length=2000)
    created_by: Optional[str] = Field(default="operator", max_length=120)


class TopicPackageUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    summary: Optional[str] = Field(default=None, max_length=5000)
    content_angle: Optional[str] = Field(default=None, max_length=200)
    priority: Optional[str] = None
    target_content_type: Optional[str] = Field(default=None, max_length=60)
    target_platforms: Optional[list[str]] = None
    operator_note: Optional[str] = Field(default=None, max_length=2000)


class TopicPackageStatusUpdate(BaseModel):
    status: str


class TopicPackageFromContentItemsRequest(TopicPackageCreate):
    content_item_ids: list[str] = Field(min_length=1, max_length=100)
    primary_content_item_id: Optional[str] = None


class TopicPackageItemBatchAddRequest(BaseModel):
    content_item_ids: list[str] = Field(min_length=1, max_length=100)


class TopicPackagePrimaryItemRequest(BaseModel):
    content_item_id: str


class TopicPackageItemsOrderRequest(BaseModel):
    ordered_content_item_ids: list[str] = Field(min_length=1, max_length=100)


class TopicPackageMergeRequest(BaseModel):
    target_topic_package_id: str
    source_topic_package_ids: list[str] = Field(min_length=1, max_length=100)
    archive_sources: bool = True
