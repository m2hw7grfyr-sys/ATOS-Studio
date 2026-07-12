from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


VALID_CONTENT_STATUSES = {"pending_review", "approved", "rejected", "archived"}


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

