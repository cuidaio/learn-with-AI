"""
M3.6–M3.7 实体路由 — 查询/审核/编辑/导出/手动添加。
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, Entity, LearningEvent
from app.schemas import EntityItem, EntityListResponse, EntityManualCreate, EntityReviewRequest, EntityUpdateRequest
from app.core.graph_store import search_entities, lookup_entity_definition

router = APIRouter(prefix="/api/entities", tags=["entities"])


def _entity_to_item(e: Entity) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "entity_type": e.entity_type,
        "description": e.description,
        "confidence": e.confidence,
        "introduction_context": e.introduction_context,
        "filter_action": e.filter_action or "pending",
        "filter_reason": e.filter_reason,
        "source": e.source or "llm",
        "created_at": e.created_at,
    }


@router.get("", response_model=EntityListResponse)
def list_entities(
    document_id: uuid.UUID = Query(...),
    filter_action: str | None = Query(None, description="keep|review|discard|all"),
    entity_type: str | None = Query(None, description="concept|theorist|theory|method|fact"),
    search: str | None = Query(None, description="模糊搜索 name/description"),
    sort_by: str = Query("name_asc", description="name_asc|name_desc|created_asc|created_desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """获取实体列表，支持筛选、排序、搜索、分页。"""
    entities, total = search_entities(
        db,
        document_id=document_id,
        filter_action=filter_action,
        entity_type=entity_type,
        search=search,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return EntityListResponse(
        entities=[EntityItem(**_entity_to_item(e)) for e in entities],
        total=total,
        filters={
            "filter_action": filter_action,
            "entity_type": entity_type,
            "search": search,
            "sort_by": sort_by,
            "limit": limit,
            "offset": offset,
        },
    )


@router.get("/lookup")
def lookup_entity(
    name: str = Query(..., description="实体名称"),
    document_id: uuid.UUID = Query(..., description="当前文档 ID（排除同文档定义）"),
    db: Session = Depends(get_db),
):
    """跨文档查找实体定义（仅限已确认实体，优先返回其他文档的定义）。"""
    result = lookup_entity_definition(db, name, exclude_document_id=document_id)
    if not result or not result.get("introduction_context"):
        raise HTTPException(status_code=404, detail="Entity definition not found")
    return result


@router.put("/{entity_id}", response_model=EntityItem)
def update_entity(
    entity_id: uuid.UUID,
    payload: EntityUpdateRequest,
    db: Session = Depends(get_db),
):
    """编辑实体字段。"""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    changed_fields = {}
    if payload.name is not None:
        entity.name = payload.name.strip()
        changed_fields["name"] = payload.name.strip()
    if payload.entity_type is not None:
        entity.entity_type = payload.entity_type
        changed_fields["entity_type"] = payload.entity_type
    if payload.description is not None:
        entity.description = payload.description.strip()
        changed_fields["description"] = payload.description.strip()
    if payload.introduction_context is not None:
        entity.introduction_context = payload.introduction_context.strip()
        changed_fields["introduction_context"] = payload.introduction_context.strip()
    if payload.filter_action is not None:
        if payload.filter_action not in ("keep", "review", "discard"):
            raise HTTPException(status_code=400, detail="filter_action must be 'keep', 'review', or 'discard'")
        entity.filter_action = payload.filter_action
        entity.filter_reason = "user_edit"
        changed_fields["filter_action"] = payload.filter_action

    if changed_fields:
        # 记录学习事件
        event = LearningEvent(
            id=uuid.uuid4(),
            event_type="entity_edited",
            document_id=entity.document_id,
            entity_id=entity.id,
            context={"changed_fields": changed_fields},
        )
        db.add(event)

    db.commit()
    db.refresh(entity)
    return EntityItem(**_entity_to_item(entity))


@router.get("/export")
def export_entities(
    document_id: uuid.UUID = Query(...),
    filter_action: str | None = Query(None, description="keep|review|discard|all"),
    format: str = Query("markdown", description="markdown|json"),
    db: Session = Depends(get_db),
):
    """导出实体列表为 Markdown 或 JSON。"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    entities, total = search_entities(
        db,
        document_id=document_id,
        filter_action=filter_action,
        limit=1000,
    )

    if format == "json":
        data = {
            "export_time": datetime.utcnow().isoformat(),
            "document_id": str(document_id),
            "document_title": doc.title,
            "entity_count": total,
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "description": e.description,
                    "introduction_context": e.introduction_context,
                    "filter_action": e.filter_action,
                    "filter_reason": e.filter_reason,
                    "source": e.source,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entities
            ],
        }
        return data

    # Markdown format
    type_groups: dict[str, list[Entity]] = {}
    for e in entities:
        t = e.entity_type or "concept"
        type_groups.setdefault(t, []).append(e)

    type_labels = {"concept": "概念", "theorist": "理论家", "theory": "理论", "method": "方法", "fact": "事实"}
    action_labels = {"keep": "已确认", "review": "待审核", "discard": "已过滤", "pending": "待处理"}

    lines = [
        f"# 实体列表 — {doc.title}",
        f"导出时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"实体数量：{total}",
        "",
    ]

    type_order = ["concept", "theorist", "theory", "method", "fact"]
    seen_types = set()
    for t in type_order:
        if t not in type_groups:
            continue
        seen_types.add(t)
        group = type_groups[t]
        label = type_labels.get(t, t)
        lines.append(f"## {label} ({len(group)})")
        lines.append("")
        for e in group:
            lines.append(f"### {e.name}")
            lines.append(f"- 类型：{type_labels.get(e.entity_type or 'concept', e.entity_type or 'concept')}")
            lines.append(f"- 状态：{action_labels.get(e.filter_action or 'pending', e.filter_action or 'pending')}")
            lines.append(f"- 来源：{'手动添加' if e.source == 'manual' else 'LLM'}")
            if e.description:
                lines.append(f"- 描述：{e.description}")
            if e.introduction_context:
                lines.append(f"- 上下文：{e.introduction_context}")
            lines.append("")

    # 剩余未覆盖的类型
    for t, group in type_groups.items():
        if t in seen_types:
            continue
        lines.append(f"## {t} ({len(group)})")
        lines.append("")
        for e in group:
            lines.append(f"### {e.name}")
            lines.append(f"- 类型：{e.entity_type}")
            lines.append(f"- 状态：{action_labels.get(e.filter_action or 'pending', e.filter_action or 'pending')}")
            lines.append(f"- 来源：{'手动添加' if e.source == 'manual' else 'LLM'}")
            if e.description:
                lines.append(f"- 描述：{e.description}")
            if e.introduction_context:
                lines.append(f"- 上下文：{e.introduction_context}")
            lines.append("")

    content = "\n".join(lines)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="entities_{document_id}.md"'},
    )


@router.put("/{entity_id}/review")
def review_entity(
    entity_id: uuid.UUID,
    payload: EntityReviewRequest,
    db: Session = Depends(get_db),
):
    """用户审批实体：确认保留或标记丢弃。"""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if payload.action not in ("keep", "discard"):
        raise HTTPException(status_code=400, detail="action must be 'keep' or 'discard'")
    entity.filter_action = payload.action
    entity.filter_reason = "user_review" if payload.action == "keep" else "user_discard"
    db.commit()
    return {"status": "ok", "filter_action": entity.filter_action}


@router.post("/manual", response_model=EntityItem, status_code=201)
def create_manual_entity(
    payload: EntityManualCreate,
    db: Session = Depends(get_db),
):
    """用户手动添加实体（从阅读器选中文本）。"""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    entity = Entity(
        id=uuid.uuid4(),
        document_id=payload.document_id,
        name=payload.name.strip(),
        entity_type=payload.entity_type,
        description=payload.description.strip(),
        introduction_context=payload.introduction_context.strip(),
        filter_action="keep",
        filter_reason="manual_add",
        source="manual",
        confidence=1.0,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return EntityItem(**_entity_to_item(entity))
