from __future__ import annotations

import hashlib
import json
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.content_item import StudioContentItem
from models.content_item import utc_now
from models.schemas import AtosContentItem, StudioContentItemRead, StudioContentPushRequest


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def parse_json(value: str, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def source_hash_for(item: AtosContentItem) -> str:
    if item.source_platform and item.source_post_id:
        key = f"platform-post:{item.source_platform.lower()}:{item.source_post_id}"
    elif item.atos_post_id:
        key = f"atos-post:{item.atos_post_id}"
    elif item.source_url:
        key = f"url:{item.source_url.strip().lower()}"
    else:
        key = f"content:{item.source_platform.lower()}:{item.title.strip()}:{item.body.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def serialize_item(item: StudioContentItem) -> StudioContentItemRead:
    return StudioContentItemRead(
        id=item.id,
        source_platform=item.source_platform,
        atos_post_id=item.atos_post_id,
        source_post_id=item.source_post_id,
        source_url=item.source_url,
        title=item.title,
        body=item.body,
        author=item.author,
        published_at=item.published_at,
        collected_at=item.collected_at,
        source_score=item.source_score,
        comment_count=item.comment_count,
        risk_level=item.risk_level,
        tags=parse_json(item.tags_json, []),
        metadata=parse_json(item.metadata_json, {}),
        source_snapshot=parse_json(item.source_snapshot_json, {}),
        source_hash=item.source_hash,
        status=item.status,
        source_type=item.source_type,
        requested_content_type=item.requested_content_type,
        target_platforms=parse_json(item.target_platforms_json, []),
        operator_note=item.operator_note,
        review_note=item.review_note,
        reviewed_at=item.reviewed_at,
        approved_at=item.approved_at,
        rejected_at=item.rejected_at,
        archived_at=item.archived_at,
        last_pushed_at=item.last_pushed_at,
        push_count=item.push_count or 0,
        imported_at=item.imported_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class ContentItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_duplicate(self, source_platform: str, source_post_id: Optional[str], atos_post_id: Optional[str], source_hash: str) -> Optional[StudioContentItem]:
        conditions = [StudioContentItem.source_hash == source_hash]
        if source_post_id:
            conditions.append(
                (StudioContentItem.source_platform == source_platform)
                & (StudioContentItem.source_post_id == source_post_id)
            )
        if atos_post_id:
            conditions.append(StudioContentItem.atos_post_id == atos_post_id)
        return self.db.scalar(select(StudioContentItem).where(or_(*conditions)).limit(1))

    def import_from_atos(self, item: AtosContentItem) -> tuple[StudioContentItem, bool]:
        source_hash = source_hash_for(item)
        existing = self.find_duplicate(
            item.source_platform,
            item.source_post_id,
            item.atos_post_id,
            source_hash,
        )
        if existing:
            return existing, False
        row = StudioContentItem(
            source_platform=item.source_platform,
            atos_post_id=item.atos_post_id,
            source_post_id=item.source_post_id,
            source_url=item.source_url,
            title=item.title,
            body=item.body or "",
            author=item.author,
            published_at=item.published_at,
            collected_at=item.collected_at,
            source_score=item.score,
            comment_count=item.comment_count,
            risk_level=item.risk_level,
            tags_json=stable_json(item.tags),
            metadata_json=stable_json(item.metadata),
            source_snapshot_json=stable_json(item.model_dump(mode="json")),
            source_hash=source_hash,
            status="pending_review",
            source_type="manual_import",
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def push_from_atos(self, payload: StudioContentPushRequest) -> tuple[StudioContentItem, bool]:
        item = payload.to_atos_content_item()
        source_hash = source_hash_for(item)
        existing = self.find_duplicate(
            item.source_platform,
            item.source_post_id,
            item.atos_post_id,
            source_hash,
        )
        now = utc_now()
        context = payload.push_context
        if existing:
            existing.last_pushed_at = now
            existing.push_count = (existing.push_count or 0) + 1
            existing.requested_content_type = context.requested_content_type or existing.requested_content_type
            existing.target_platforms_json = stable_json(context.target_platforms or parse_json(existing.target_platforms_json, []))
            existing.operator_note = context.operator_note or existing.operator_note
            existing.source_snapshot_json = stable_json(
                {
                    **parse_json(existing.source_snapshot_json, {}),
                    "last_push_snapshot": payload.model_dump(mode="json"),
                }
            )
            self.db.flush()
            return existing, False

        row = StudioContentItem(
            source_platform=item.source_platform,
            atos_post_id=item.atos_post_id,
            source_post_id=item.source_post_id,
            source_url=item.source_url,
            title=item.title,
            body=item.body or "",
            author=item.author,
            published_at=item.published_at,
            collected_at=item.collected_at,
            source_score=item.score,
            comment_count=item.comment_count,
            risk_level=item.risk_level,
            tags_json=stable_json(item.tags),
            metadata_json=stable_json(item.metadata),
            source_snapshot_json=stable_json(payload.model_dump(mode="json")),
            source_hash=source_hash,
            status="pending_review",
            source_type="atos_manual_push",
            requested_content_type=context.requested_content_type,
            target_platforms_json=stable_json(context.target_platforms),
            operator_note=context.operator_note,
            last_pushed_at=now,
            push_count=1,
        )
        self.db.add(row)
        self.db.flush()
        return row, True

    def find_by_source(
        self,
        source_platform: str,
        source_post_id: Optional[str] = None,
        atos_post_id: Optional[str] = None,
    ) -> Optional[StudioContentItem]:
        conditions = []
        platform = source_platform.lower()
        if source_post_id:
            conditions.append(
                (StudioContentItem.source_platform == platform)
                & (StudioContentItem.source_post_id == source_post_id)
            )
        if atos_post_id:
            conditions.append(StudioContentItem.atos_post_id == atos_post_id)
        if not conditions:
            return None
        return self.db.scalar(select(StudioContentItem).where(or_(*conditions)).limit(1))

    def list(
        self,
        status: Optional[str],
        platform: Optional[str],
        search: Optional[str],
        limit: int,
        offset: int,
        source_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        target_content_type: Optional[str] = None,
    ) -> tuple[list[StudioContentItem], int]:
        statement = select(StudioContentItem)
        if status:
            statement = statement.where(StudioContentItem.status == status)
        if platform:
            statement = statement.where(StudioContentItem.source_platform == platform.lower())
        if source_type:
            statement = statement.where(StudioContentItem.source_type == source_type)
        if risk_level:
            statement = statement.where(StudioContentItem.risk_level == risk_level)
        if target_content_type:
            statement = statement.where(StudioContentItem.requested_content_type == target_content_type)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    StudioContentItem.title.ilike(pattern),
                    StudioContentItem.body.ilike(pattern),
                    StudioContentItem.author.ilike(pattern),
                )
            )
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.db.scalars(
            statement.order_by(StudioContentItem.imported_at.desc()).offset(offset).limit(limit)
        ).all()
        return list(rows), total
