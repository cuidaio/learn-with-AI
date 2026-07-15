"""
M2.8 知识图谱查询路由。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.graph_store import get_entities, get_full_graph
from app.database import get_db
from app.models import Document
from app.schemas import (
    EntityItem,
    KnowledgeGraphResponse,
    RelationItem,
)

router = APIRouter(prefix="/api/documents", tags=["graph"])


@router.get("/{id}/entities", response_model=list[EntityItem])
def list_entities(id: uuid.UUID, db: Session = Depends(get_db)):
    """获取文档的所有实体。"""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    entities = get_entities(db, id)
    return [
        EntityItem(id=e.id, name=e.name, entity_type=e.entity_type, description=e.description, confidence=e.confidence)
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
