from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.content_item import StudioContentItem, utc_now
from models.schemas import (
    VALID_CONTENT_STATUSES,
    VALID_RISK_LEVELS,
    VALID_TOPIC_PACKAGE_STATUSES,
    VALID_TOPIC_PRIORITIES,
    TopicPackageCreate,
    TopicPackageFromContentItemsRequest,
    TopicPackageUpdate,
)
from models.topic_package import StudioAuditEvent, StudioTopicPackage, StudioTopicPackageItem
from repositories.content_items import parse_json, serialize_item, stable_json


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", title.lower(), flags=re.UNICODE)).strip()


def token_set(value: str) -> set[str]:
    return {token for token in normalize_title(value).split() if len(token) > 2}


def risk_rank(value: Optional[str]) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get((value or "").lower(), 0)


def safe_package_status(status: str) -> str:
    if status not in VALID_TOPIC_PACKAGE_STATUSES:
        raise HTTPException(status_code=422, detail="invalid topic package status")
    return status


def safe_content_status(status: str) -> str:
    if status not in VALID_CONTENT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid content item status")
    return status


def safe_priority(priority: str) -> str:
    if priority not in VALID_TOPIC_PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid topic package priority")
    return priority


def audit_event(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
) -> None:
    db.add(
        StudioAuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=stable_json(before or {}),
            after_json=stable_json(after or {}),
            metadata_json=stable_json(metadata or {}),
        )
    )


def apply_content_status(row: StudioContentItem, status: str, review_note: str = "") -> None:
    safe_content_status(status)
    now = utc_now()
    row.status = status
    row.reviewed_at = now
    if review_note:
        row.review_note = review_note
    if status == "approved":
        row.approved_at = now
    elif status == "rejected":
        row.rejected_at = now
    elif status == "archived":
        row.archived_at = now


def update_content_status_with_audit(
    db: Session,
    item_id: str,
    status: str,
    review_note: str = "",
) -> StudioContentItem:
    row = db.get(StudioContentItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="content item not found")
    before = {"status": row.status, "review_note": row.review_note}
    apply_content_status(row, status, review_note)
    db.flush()
    audit_event(
        db,
        "studio_content_item",
        row.id,
        "content_status_changed",
        before,
        {"status": row.status, "review_note": row.review_note},
    )
    return row


def batch_update_content_status(
    db: Session,
    content_item_ids: list[str],
    status: str,
    review_note: str = "",
) -> dict:
    safe_content_status(status)
    seen = list(dict.fromkeys(content_item_ids))
    results = []
    updated = 0
    for item_id in seen:
        row = db.get(StudioContentItem, item_id)
        if not row:
            results.append({"content_item_id": item_id, "success": False, "status": None, "error": "not_found"})
            continue
        before = {"status": row.status, "review_note": row.review_note}
        apply_content_status(row, status, review_note)
        audit_event(
            db,
            "studio_content_item",
            row.id,
            "content_status_changed",
            before,
            {"status": row.status, "review_note": row.review_note},
            {"batch": True},
        )
        updated += 1
        results.append({"content_item_id": item_id, "success": True, "status": row.status, "error": None})
    db.flush()
    return {"total": len(seen), "updated": updated, "failed": len(seen) - updated, "results": results}


def content_topic_memberships(db: Session, content_item_id: str) -> list[dict]:
    rows = db.execute(
        select(StudioTopicPackage, StudioTopicPackageItem)
        .join(StudioTopicPackageItem, StudioTopicPackageItem.topic_package_id == StudioTopicPackage.id)
        .where(
            StudioTopicPackageItem.content_item_id == content_item_id,
            StudioTopicPackageItem.removed_at.is_(None),
        )
        .order_by(StudioTopicPackage.updated_at.desc())
    ).all()
    return [
        {
            "topic_package_id": package.id,
            "title": package.title,
            "status": package.status,
            "is_primary": link.is_primary,
            "added_at": link.added_at.isoformat() if link.added_at else None,
        }
        for package, link in rows
    ]


def serialize_audit(event: StudioAuditEvent) -> dict:
    return {
        "id": event.id,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "action": event.action,
        "before": parse_json(event.before_json, {}),
        "after": parse_json(event.after_json, {}),
        "metadata": parse_json(event.metadata_json, {}),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def serialize_topic_item(db: Session, link: StudioTopicPackageItem) -> dict:
    row = db.get(StudioContentItem, link.content_item_id)
    item = serialize_item(row).model_dump(mode="json") if row else None
    return {
        "id": link.id,
        "topic_package_id": link.topic_package_id,
        "content_item_id": link.content_item_id,
        "position": link.position,
        "is_primary": link.is_primary,
        "added_at": link.added_at.isoformat() if link.added_at else None,
        "removed_at": link.removed_at.isoformat() if link.removed_at else None,
        "content_item": item,
    }


def active_links(db: Session, topic_package_id: str) -> list[StudioTopicPackageItem]:
    return list(
        db.scalars(
            select(StudioTopicPackageItem)
            .where(
                StudioTopicPackageItem.topic_package_id == topic_package_id,
                StudioTopicPackageItem.removed_at.is_(None),
            )
            .order_by(StudioTopicPackageItem.position.asc(), StudioTopicPackageItem.added_at.asc())
        ).all()
    )


def recalculate_topic_package(db: Session, package: StudioTopicPackage) -> StudioTopicPackage:
    links = active_links(db, package.id)
    rows = [db.get(StudioContentItem, link.content_item_id) for link in links]
    rows = [row for row in rows if row is not None]
    scores = [row.source_score for row in rows if row.source_score is not None]
    risk_values = [(row.risk_level or "unknown").lower() for row in rows]
    package.source_count = len(rows)
    package.total_comment_count = sum(row.comment_count or 0 for row in rows)
    package.average_source_score = round(sum(scores) / len(scores), 2) if scores else None
    package.max_source_score = max(scores) if scores else None
    if "high" in risk_values:
        package.risk_level = "high"
    elif "medium" in risk_values:
        package.risk_level = "medium"
    elif rows and all(value == "low" for value in risk_values):
        package.risk_level = "low"
    else:
        package.risk_level = "unknown"
    package.updated_at = utc_now()
    db.flush()
    return package


def find_similar_topic_packages(db: Session, title: str, exclude_id: Optional[str] = None, limit: int = 8) -> list[dict]:
    normalized = normalize_title(title)
    tokens = token_set(title)
    statement = select(StudioTopicPackage)
    if exclude_id:
        statement = statement.where(StudioTopicPackage.id != exclude_id)
    candidates = db.scalars(statement.order_by(StudioTopicPackage.updated_at.desc()).limit(200)).all()
    matches = []
    for package in candidates:
        reasons = []
        score = 0.0
        if package.normalized_title == normalized and normalized:
            reasons.append("标题规范化后完全一致")
            score = 1.0
        else:
            other_tokens = token_set(package.title)
            union = tokens | other_tokens
            jaccard = len(tokens & other_tokens) / len(union) if union else 0.0
            if jaccard >= 0.45:
                reasons.append(f"标题关键词重叠 {jaccard:.2f}")
                score = jaccard
        if reasons:
            matches.append(
                {
                    "topic_package_id": package.id,
                    "title": package.title,
                    "status": package.status,
                    "source_count": package.source_count,
                    "risk_level": package.risk_level,
                    "similarity_score": score,
                    "reasons": reasons,
                }
            )
    matches.sort(key=lambda item: item["similarity_score"], reverse=True)
    return matches[:limit]


def serialize_topic_package(db: Session, package: StudioTopicPackage, include_items: bool = False, include_audit: bool = False) -> dict:
    payload = {
        "id": package.id,
        "title": package.title,
        "normalized_title": package.normalized_title,
        "summary": package.summary,
        "content_angle": package.content_angle,
        "status": package.status,
        "risk_level": package.risk_level,
        "priority": package.priority,
        "source_count": package.source_count,
        "total_comment_count": package.total_comment_count,
        "average_source_score": package.average_source_score,
        "max_source_score": package.max_source_score,
        "target_content_type": package.target_content_type,
        "target_platforms": parse_json(package.target_platforms_json, []),
        "operator_note": package.operator_note,
        "created_by": package.created_by,
        "merged_into_topic_package_id": package.merged_into_topic_package_id,
        "approved_at": package.approved_at.isoformat() if package.approved_at else None,
        "rejected_at": package.rejected_at.isoformat() if package.rejected_at else None,
        "archived_at": package.archived_at.isoformat() if package.archived_at else None,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None,
        "possible_duplicates": find_similar_topic_packages(db, package.title, exclude_id=package.id),
    }
    if include_items:
        payload["items"] = [serialize_topic_item(db, link) for link in active_links(db, package.id)]
        platforms: dict[str, int] = {}
        risks: dict[str, int] = {}
        for item in payload["items"]:
            source = item.get("content_item") or {}
            platform = source.get("source_platform") or "unknown"
            risk = source.get("risk_level") or "unknown"
            platforms[platform] = platforms.get(platform, 0) + 1
            risks[risk] = risks.get(risk, 0) + 1
        payload["platform_distribution"] = platforms
        payload["risk_distribution"] = risks
    if include_audit:
        events = db.scalars(
            select(StudioAuditEvent)
            .where(StudioAuditEvent.entity_id == package.id)
            .order_by(StudioAuditEvent.created_at.desc())
            .limit(100)
        ).all()
        payload["audit_events"] = [serialize_audit(event) for event in events]
    return payload


def list_topic_packages(
    db: Session,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    risk_level: Optional[str] = None,
    target_platform: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    statement = select(StudioTopicPackage)
    if status:
        statement = statement.where(StudioTopicPackage.status == safe_package_status(status))
    if priority:
        statement = statement.where(StudioTopicPackage.priority == safe_priority(priority))
    if risk_level:
        if risk_level not in VALID_RISK_LEVELS:
            raise HTTPException(status_code=422, detail="invalid risk level")
        statement = statement.where(StudioTopicPackage.risk_level == risk_level)
    if target_platform:
        statement = statement.where(StudioTopicPackage.target_platforms_json.ilike(f"%{target_platform}%"))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(StudioTopicPackage.title.ilike(pattern), StudioTopicPackage.summary.ilike(pattern))
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(StudioTopicPackage.updated_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [serialize_topic_package(db, row) for row in rows], "total": total, "limit": limit, "offset": offset}


def create_topic_package(db: Session, payload: TopicPackageCreate) -> StudioTopicPackage:
    safe_priority(payload.priority)
    package = StudioTopicPackage(
        title=payload.title.strip(),
        normalized_title=normalize_title(payload.title),
        summary=payload.summary or "",
        content_angle=payload.content_angle,
        status="pending_review",
        risk_level="unknown",
        priority=payload.priority,
        target_content_type=payload.target_content_type,
        target_platforms_json=stable_json(payload.target_platforms),
        operator_note=payload.operator_note,
        created_by=payload.created_by,
    )
    db.add(package)
    db.flush()
    audit_event(db, "studio_topic_package", package.id, "topic_package_created", after=serialize_topic_package(db, package))
    return package


def create_topic_package_from_content_items(db: Session, payload: TopicPackageFromContentItemsRequest) -> StudioTopicPackage:
    ids = list(dict.fromkeys(payload.content_item_ids))
    missing = [item_id for item_id in ids if db.get(StudioContentItem, item_id) is None]
    if missing:
        raise HTTPException(status_code=422, detail={"message": "content items not found", "missing": missing})
    package = create_topic_package(db, payload)
    add_items_to_topic_package(db, package.id, ids, primary_content_item_id=payload.primary_content_item_id or ids[0])
    audit_event(db, "studio_topic_package", package.id, "topic_package_created_from_content_items", metadata={"content_item_ids": ids})
    return db.get(StudioTopicPackage, package.id) or package


def add_items_to_topic_package(
    db: Session,
    topic_package_id: str,
    content_item_ids: list[str],
    primary_content_item_id: Optional[str] = None,
) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    ids = list(dict.fromkeys(content_item_ids))
    if len(ids) > 100:
        raise HTTPException(status_code=422, detail="too many content items")
    existing_links = {
        link.content_item_id: link
        for link in db.scalars(
            select(StudioTopicPackageItem).where(StudioTopicPackageItem.topic_package_id == topic_package_id)
        ).all()
    }
    max_position = max((link.position for link in existing_links.values() if link.removed_at is None), default=0)
    results = []
    for item_id in ids:
        if not db.get(StudioContentItem, item_id):
            results.append({"content_item_id": item_id, "status": "failed", "error": "not_found"})
            continue
        link = existing_links.get(item_id)
        if link and link.removed_at is None:
            results.append({"content_item_id": item_id, "status": "duplicate", "error": None})
            continue
        if link and link.removed_at is not None:
            link.removed_at = None
            link.added_at = utc_now()
            max_position += 1
            link.position = max_position
            results.append({"content_item_id": item_id, "status": "restored", "error": None})
            continue
        max_position += 1
        db.add(
            StudioTopicPackageItem(
                topic_package_id=topic_package_id,
                content_item_id=item_id,
                position=max_position,
                is_primary=False,
            )
        )
        results.append({"content_item_id": item_id, "status": "added", "error": None})
    db.flush()
    links = active_links(db, topic_package_id)
    if primary_content_item_id:
        set_primary_item(db, topic_package_id, primary_content_item_id, audit=False)
    elif links and not any(link.is_primary for link in links):
        set_primary_item(db, topic_package_id, links[0].content_item_id, audit=False)
    recalculate_topic_package(db, package)
    audit_event(db, "studio_topic_package", topic_package_id, "topic_package_items_added", metadata={"results": results})
    return {"results": results, "topic_package": serialize_topic_package(db, package, include_items=True)}


def remove_item_from_topic_package(db: Session, topic_package_id: str, content_item_id: str) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    link = db.scalar(
        select(StudioTopicPackageItem).where(
            StudioTopicPackageItem.topic_package_id == topic_package_id,
            StudioTopicPackageItem.content_item_id == content_item_id,
            StudioTopicPackageItem.removed_at.is_(None),
        )
    )
    if not link:
        raise HTTPException(status_code=404, detail="topic package item not found")
    was_primary = link.is_primary
    link.removed_at = utc_now()
    link.is_primary = False
    db.flush()
    if was_primary:
        remaining = active_links(db, topic_package_id)
        if remaining:
            set_primary_item(db, topic_package_id, remaining[0].content_item_id, audit=False)
    recalculate_topic_package(db, package)
    audit_event(
        db,
        "studio_topic_package",
        topic_package_id,
        "topic_package_item_removed",
        metadata={"content_item_id": content_item_id, "was_primary": was_primary},
    )
    return serialize_topic_package(db, package, include_items=True)


def set_primary_item(db: Session, topic_package_id: str, content_item_id: str, audit: bool = True) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    links = active_links(db, topic_package_id)
    target = next((link for link in links if link.content_item_id == content_item_id), None)
    if not target:
        raise HTTPException(status_code=422, detail="content item is not an active package member")
    before = [link.content_item_id for link in links if link.is_primary]
    for link in links:
        link.is_primary = link.content_item_id == content_item_id
    db.flush()
    if audit:
        audit_event(
            db,
            "studio_topic_package",
            topic_package_id,
            "topic_package_primary_item_set",
            before={"primary": before},
            after={"primary": content_item_id},
        )
    return serialize_topic_package(db, package, include_items=True)


def reorder_topic_items(db: Session, topic_package_id: str, ordered_content_item_ids: list[str]) -> dict:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    links = active_links(db, topic_package_id)
    current_ids = [link.content_item_id for link in links]
    ordered = list(dict.fromkeys(ordered_content_item_ids))
    if set(ordered) != set(current_ids) or len(ordered) != len(current_ids):
        raise HTTPException(status_code=422, detail="ordered_content_item_ids must exactly match active members")
    link_by_content = {link.content_item_id: link for link in links}
    for position, item_id in enumerate(ordered, start=1):
        link_by_content[item_id].position = position
    db.flush()
    audit_event(db, "studio_topic_package", topic_package_id, "topic_package_items_reordered", after={"ordered_content_item_ids": ordered})
    return serialize_topic_package(db, package, include_items=True)


def update_topic_package(db: Session, topic_package_id: str, payload: TopicPackageUpdate) -> StudioTopicPackage:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    before = serialize_topic_package(db, package)
    data = payload.model_dump(exclude_unset=True)
    if "priority" in data and data["priority"] is not None:
        safe_priority(data["priority"])
    if "title" in data and data["title"]:
        package.title = data["title"].strip()
        package.normalized_title = normalize_title(package.title)
    for key in ["summary", "content_angle", "priority", "target_content_type", "operator_note"]:
        if key in data:
            setattr(package, key, data[key])
    if "target_platforms" in data and data["target_platforms"] is not None:
        package.target_platforms_json = stable_json(data["target_platforms"])
    package.updated_at = utc_now()
    db.flush()
    audit_event(db, "studio_topic_package", package.id, "topic_package_updated", before=before, after=serialize_topic_package(db, package))
    return package


def update_topic_package_status(db: Session, topic_package_id: str, status: str) -> StudioTopicPackage:
    package = db.get(StudioTopicPackage, topic_package_id)
    if not package:
        raise HTTPException(status_code=404, detail="topic package not found")
    safe_package_status(status)
    before = {"status": package.status}
    now = utc_now()
    package.status = status
    if status == "approved":
        package.approved_at = now
    elif status == "rejected":
        package.rejected_at = now
    elif status == "archived":
        package.archived_at = now
    package.updated_at = now
    db.flush()
    audit_event(db, "studio_topic_package", package.id, "topic_package_status_changed", before=before, after={"status": status})
    return package


def merge_topic_packages(
    db: Session,
    target_topic_package_id: str,
    source_topic_package_ids: list[str],
    archive_sources: bool = True,
) -> dict:
    target = db.get(StudioTopicPackage, target_topic_package_id)
    if not target:
        raise HTTPException(status_code=404, detail="target topic package not found")
    source_ids = [item for item in dict.fromkeys(source_topic_package_ids) if item != target_topic_package_id]
    moved: list[str] = []
    for source_id in source_ids:
        source = db.get(StudioTopicPackage, source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"source topic package not found: {source_id}")
        ids = [link.content_item_id for link in active_links(db, source_id)]
        moved.extend(ids)
        add_items_to_topic_package(db, target_topic_package_id, ids)
        source.merged_into_topic_package_id = target_topic_package_id
        if archive_sources:
            update_topic_package_status(db, source_id, "archived")
    recalculate_topic_package(db, target)
    audit_event(
        db,
        "studio_topic_package",
        target_topic_package_id,
        "topic_package_merged",
        metadata={"source_topic_package_ids": source_ids, "moved_content_item_ids": list(dict.fromkeys(moved))},
    )
    return {
        "target": serialize_topic_package(db, target, include_items=True),
        "source_topic_package_ids": source_ids,
        "moved_content_item_ids": list(dict.fromkeys(moved)),
        "archive_sources": archive_sources,
    }


def topic_package_audit_events(db: Session, topic_package_id: str) -> list[dict]:
    events = db.scalars(
        select(StudioAuditEvent)
        .where(
            or_(
                and_(StudioAuditEvent.entity_type == "studio_topic_package", StudioAuditEvent.entity_id == topic_package_id),
                StudioAuditEvent.metadata_json.ilike(f"%{topic_package_id}%"),
            )
        )
        .order_by(StudioAuditEvent.created_at.desc())
        .limit(100)
    ).all()
    return [serialize_audit(event) for event in events]


def topic_package_stats(db: Session) -> dict:
    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "pending_review": db.scalar(select(func.count()).where(StudioTopicPackage.status == "pending_review")) or 0,
        "approved": db.scalar(select(func.count()).where(StudioTopicPackage.status == "approved")) or 0,
        "created_today": db.scalar(select(func.count()).where(StudioTopicPackage.created_at >= today_start)) or 0,
    }
