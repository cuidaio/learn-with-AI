"""
M2.8 知识图谱查询路由。
M3.9 新增邻域查询 + 路径查询（G6 增量图谱浏览器后端）。
"""

import uuid
from collections import deque

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.graph_store import get_entities, get_full_graph
from app.database import get_db
from app.models import Document, Entity, Relation
from app.schemas import (
    EntityItem,
    KnowledgeGraphResponse,
    NeighborsResponse,
    NeighborItem,
    NeighborEntityItem,
    NeighborRelationItem,
    PathResponse,
    PathEdgeItem,
    RelationItem,
    RelationManualCreate,
    RelationManualCreateResponse,
    RelationManualUpdate,
)

router = APIRouter(prefix="/api/documents", tags=["graph"])
graph_browser_router = APIRouter(prefix="/api/graph", tags=["graph_browser"])


@router.get("/{id}/entities", response_model=list[EntityItem])
def list_entities(id: uuid.UUID, db: Session = Depends(get_db)):
    """获取文档的所有实体。"""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    entities = get_entities(db, id)
    return [
        EntityItem(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            description=e.description,
            confidence=e.confidence,
            introduction_context=e.introduction_context,
            filter_action=e.filter_action or "pending",
            filter_reason=e.filter_reason,
            source=e.source or "llm",
            created_at=e.created_at,
        )
        for e in entities
    ]


@router.get("/{id}/relations", response_model=list[RelationItem])
def list_relations(id: uuid.UUID, db: Session = Depends(get_db)):
    """获取文档的所有关系。"""
    from app.core.graph_store import get_relations as _get_rels
    from app.models import Entity as EntModel

    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    rels = _get_rels(db, id)
    entity_map = {str(e.id): e.name for e in db.query(EntModel).filter(EntModel.document_id == id).all()}

    return [
        RelationItem(
            id=r.id,
            source_entity_id=r.source_entity_id,
            target_entity_id=r.target_entity_id,
            relation_type=r.relation_type,
            description=r.description or "",
            source_name=entity_map.get(str(r.source_entity_id), ""),
            target_name=entity_map.get(str(r.target_entity_id), ""),
        )
        for r in rels
    ]


@router.get("/{id}/knowledge-graph", response_model=KnowledgeGraphResponse)
def get_knowledge_graph(id: uuid.UUID, db: Session = Depends(get_db)):
    """获取文档的完整知识图谱（实体 + 关系）。"""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    graph = get_full_graph(db, id)
    return KnowledgeGraphResponse(
        document_id=id,
        document_title=graph.get("document_title", doc.title),
        entities=[EntityItem(**e) for e in graph.get("entities", [])],
        relations=[
            RelationItem(
                id=r["id"],
                source_entity_id=r["source_entity_id"],
                target_entity_id=r["target_entity_id"],
                relation_type=r["relation_type"],
                description=r.get("description", ""),
                source_name=r.get("source_name", ""),
                target_name=r.get("target_name", ""),
            )
            for r in graph.get("relations", [])
        ],
    )


# ── M3.9 图谱浏览器接口 ──────────────────────────────────────────────────


@graph_browser_router.put("/relations/{relation_id}", response_model=RelationManualCreateResponse)
def update_relation(relation_id: str, body: RelationManualUpdate, db: Session = Depends(get_db)):
    """更新一条关系（修改类型/描述）。"""
    rel_uuid = uuid.UUID(relation_id)
    rel = db.query(Relation).filter(Relation.id == rel_uuid).first()
    if not rel:
        raise HTTPException(404, "Relation not found")
    if body.relation_type is not None:
        rel.relation_type = body.relation_type
    if body.description is not None:
        rel.description = body.description
    db.commit()
    db.refresh(rel)
    return RelationManualCreateResponse(
        id=rel.id,
        source_entity_id=rel.source_entity_id,
        target_entity_id=rel.target_entity_id,
        relation_type=rel.relation_type,
    )


@graph_browser_router.delete("/relations/{relation_id}")
def delete_relation(relation_id: str, db: Session = Depends(get_db)):
    """删除一条关系。"""
    rel_uuid = uuid.UUID(relation_id)
    rel = db.query(Relation).filter(Relation.id == rel_uuid).first()
    if not rel:
        raise HTTPException(404, "Relation not found")
    db.delete(rel)
    db.commit()
    return {"status": "deleted"}


@graph_browser_router.post("/relations", response_model=RelationManualCreateResponse)
def create_relation(body: RelationManualCreate, db: Session = Depends(get_db)):
    """手动创建一条关系（补连）。"""
    src = db.query(Entity).filter(Entity.id == body.source_entity_id).first()
    tgt = db.query(Entity).filter(Entity.id == body.target_entity_id).first()
    if not src or not tgt:
        raise HTTPException(404, "Entity not found")
    if src.document_id != tgt.document_id:
        raise HTTPException(400, "Entities must be in the same document")

    rel = Relation(
        document_id=src.document_id,
        source_entity_id=body.source_entity_id,
        target_entity_id=body.target_entity_id,
        relation_type=body.relation_type,
        description=body.description,
        confidence=1.0,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return RelationManualCreateResponse(
        id=rel.id,
        source_entity_id=rel.source_entity_id,
        target_entity_id=rel.target_entity_id,
        relation_type=rel.relation_type,
    )


@graph_browser_router.get("/neighbors", response_model=NeighborsResponse)
def get_neighbors(
    entity_id: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """获取指定实体的邻域（1 跳邻居，仅已确认的实体）。

    Args:
        entity_id: 实体 UUID
        limit: 每页数量
        offset: 分页偏移
    """
    entity_uuid = uuid.UUID(entity_id)
    entity = db.query(Entity).filter(
        Entity.id == entity_uuid,
        Entity.filter_action == "keep",
    ).first()
    if not entity:
        raise HTTPException(404, "Entity not found")

    # 查询该实体的所有关系（同一文档内）
    relations = db.query(Relation).filter(
        Relation.document_id == entity.document_id,
        (Relation.source_entity_id == entity_uuid) | (Relation.target_entity_id == entity_uuid),
    ).all()

    # 提取邻居 ID
    neighbor_ids: set[uuid.UUID] = set()
    for r in relations:
        if r.source_entity_id == entity_uuid:
            neighbor_ids.add(r.target_entity_id)
        else:
            neighbor_ids.add(r.source_entity_id)

    if not neighbor_ids:
        return NeighborsResponse(
            entity=NeighborEntityItem(id=entity.id, name=entity.name, entity_type=entity.entity_type, score=entity.confidence or 0),
            neighbors=[],
            has_more=False,
            total_count=0,
        )

    # 查询邻居实体（仅已确认，同一文档）
    neighbors = db.query(Entity).filter(
        Entity.id.in_(neighbor_ids),
        Entity.document_id == entity.document_id,
        Entity.filter_action == "keep",
    ).all()

    neighbors.sort(key=lambda e: e.confidence or 0, reverse=True)
    total = len(neighbors)
    paginated = neighbors[offset:offset + limit]
    has_more = total > offset + limit

    # 构建关系查询映射
    rel_map: dict[uuid.UUID, Relation] = {}
    for r in relations:
        nid = r.target_entity_id if r.source_entity_id == entity_uuid else r.source_entity_id
        rel_map[nid] = r

    neighbor_items = []
    for n in paginated:
        rel = rel_map.get(n.id)
        neighbor_items.append(NeighborItem(
            entity=NeighborEntityItem(id=n.id, name=n.name, entity_type=n.entity_type, score=n.confidence or 0),
            relation=NeighborRelationItem(
                id=rel.id if rel else uuid.uuid4(),
                relation_type=rel.relation_type if rel else "",
                description=rel.description if rel else "",
                source_entity_id=rel.source_entity_id if rel else None,
                target_entity_id=rel.target_entity_id if rel else None,
            ),
        ))

    return NeighborsResponse(
        entity=NeighborEntityItem(id=entity.id, name=entity.name, entity_type=entity.entity_type, score=entity.confidence or 0),
        neighbors=neighbor_items,
        has_more=has_more,
        total_count=total,
    )


@graph_browser_router.get("/path", response_model=PathResponse)
def get_path(
    from_id: str,
    to_id: str,
    db: Session = Depends(get_db),
):
    """计算两个实体之间的最短路径。

    在文档内部使用 BFS 算法查找路径，仅使用已确认的实体。
    """
    from_uuid = uuid.UUID(from_id)
    to_uuid = uuid.UUID(to_id)

    from_entity = db.query(Entity).filter(Entity.id == from_uuid).first()
    to_entity = db.query(Entity).filter(Entity.id == to_uuid).first()

    if not from_entity or not to_entity:
        raise HTTPException(404, "Entity not found")

    if from_entity.document_id != to_entity.document_id:
        raise HTTPException(400, "Entities must be in the same document")

    doc_id = from_entity.document_id

    # 获取文档的所有已确认实体和关系
    keep_ids = {
        e.id for e in db.query(Entity).filter(
            Entity.document_id == doc_id,
            Entity.filter_action == "keep",
        ).all()
    }

    all_relations = db.query(Relation).filter(Relation.document_id == doc_id).all()

    # 构建无向邻接表和边映射
    adj: dict[uuid.UUID, list[uuid.UUID]] = {}
    edge_map: dict[tuple[uuid.UUID, uuid.UUID], Relation] = {}
    for r in all_relations:
        if r.source_entity_id in keep_ids and r.target_entity_id in keep_ids:
            adj.setdefault(r.source_entity_id, []).append(r.target_entity_id)
            adj.setdefault(r.target_entity_id, []).append(r.source_entity_id)
            edge_map[(r.source_entity_id, r.target_entity_id)] = r
            edge_map[(r.target_entity_id, r.source_entity_id)] = r

    # BFS
    queue: deque = deque([from_uuid])
    visited: dict[uuid.UUID, uuid.UUID | None] = {from_uuid: None}

    while queue:
        current = queue.popleft()
        if current == to_uuid:
            break
        for nb in adj.get(current, []):
            if nb not in visited:
                visited[nb] = current
                queue.append(nb)

    if to_uuid not in visited:
        raise HTTPException(404, "No path found")

    # 重建路径
    path_ids: list[uuid.UUID] = []
    cur = to_uuid
    while cur is not None:
        path_ids.append(cur)
        cur = visited[cur]
    path_ids.reverse()

    # 获取实体名称映射
    name_map: dict[uuid.UUID, str] = {}
    for e in db.query(Entity).filter(Entity.document_id == doc_id).all():
        name_map[e.id] = e.name

    # 构建边列表和文本
    edges: list[dict] = []
    text_parts: list[str] = []
    for i in range(len(path_ids) - 1):
        a = path_ids[i]
        b = path_ids[i + 1]
        name_a = name_map.get(a, "?")
        name_b = name_map.get(b, "?")
        rel = edge_map.get((a, b))
        text_parts.append(name_a)
        if rel:
            edges.append(PathEdgeItem(relation_id=rel.id, from_id=a, to_id=b, label=rel.relation_type))
            text_parts.append(f"[{rel.relation_type}]")
        else:
            edges.append(PathEdgeItem(from_id=a, to_id=b, label=""))
            text_parts.append("→")
    text_parts.append(name_map.get(path_ids[-1], "?"))

    return PathResponse(
        path=path_ids,
        edges=edges,
        text=" ".join(text_parts),
    )
