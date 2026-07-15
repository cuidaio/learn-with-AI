"""
M2.8 知识图谱存储 — Entity/Relation CRUD + 事实链检索。
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Document, Entity, Relation


# ── Entity CRUD ──────────────────────────────────────────────────────────

def save_entities(
    db: Session,
    document_id: UUID,
    entity_list: list[dict],
) -> dict[str, UUID]:
    """批量保存实体，返回 {实体名称: UUID} 映射。

    Args:
        entity_list: [{"name", "type", "description"}, ...]
    """
    name_to_id: dict[str, UUID] = {}
    for item in entity_list:
        ent = Entity(
            document_id=document_id,
            name=item["name"],
            entity_type=item.get("type", "concept"),
            description=item.get("description", ""),
            confidence=1.0,
        )
        db.add(ent)
        db.flush()
        name_to_id[item["name"]] = ent.id
    return name_to_id


def get_entities(db: Session, document_id: UUID) -> list[Entity]:
    """获取文档的所有实体。"""
    return (
        db.query(Entity)
        .filter(Entity.document_id == document_id)
        .order_by(Entity.confidence.desc(), Entity.name)
        .all()
    )


def get_high_confidence_entities(db: Session, document_id: UUID, min_confidence: float = 0.7) -> list[Entity]:
    """获取置信度超过阈值的实体。"""
    return (
        db.query(Entity)
        .filter(Entity.document_id == document_id, Entity.confidence >= min_confidence)
        .order_by(Entity.confidence.desc())
        .all()
    )


def delete_entities_by_document(db: Session, document_id: UUID) -> None:
    """删除文档的所有实体（及其关联关系）。"""
    db.query(Entity).filter(Entity.document_id == document_id).delete()
    db.flush()


# ── Relation CRUD ────────────────────────────────────────────────────────

def save_relations(
    db: Session,
    document_id: UUID,
    relation_list: list[dict],
    name_to_id: dict[str, UUID],
) -> None:
    """批量保存关系。

    Args:
        relation_list: [{"source", "target", "relation_type", "description"}, ...]
        name_to_id: 实体名称 → UUID 映射。
    """
    for item in relation_list:
        source_id = name_to_id.get(item["source"])
        target_id = name_to_id.get(item["target"])
        if not source_id or not target_id:
            continue
        rel = Relation(
            document_id=document_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=item["relation_type"],
            description=item.get("description", ""),
            confidence=1.0,
        )
        db.add(rel)


def get_relations(db: Session, document_id: UUID) -> list[Relation]:
    """获取文档的所有关系。"""
    return (
        db.query(Relation)
        .filter(Relation.document_id == document_id)
        .order_by(Relation.relation_type)
        .all()
    )


def delete_relations_by_document(db: Session, document_id: UUID) -> None:
    """删除文档的所有关系。"""
    db.query(Relation).filter(Relation.document_id == document_id).delete()
    db.flush()


# ── 事实链检索 ───────────────────────────────────────────────────────────

def get_fact_chain(
    db: Session,
    document_id: UUID,
    entity_id: UUID,
    max_hops: int = 2,
) -> dict:
    """为指定实体检索事实链（实体 + 关联关系 + 1-2跳扩展）。

    Returns:
        dict with keys:
          - "entity": {"name", "type", "description"}
          - "relations": [{"source_name", "target_name", "relation_type", "description"}, ...]
          - "related_entities": [{"name", "type", "description"}, ...]
    """
    # 目标实体
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return {"entity": None, "relations": [], "related_entities": []}

    # 直接关联的关系
    direct_relations = (
        db.query(Relation)
        .filter(
            Relation.document_id == document_id,
            (Relation.source_entity_id == entity_id) | (Relation.target_entity_id == entity_id),
        )
        .all()
    )

    # 收集已涉及的实体 ID（包括目标实体）
    involved_ids = {entity_id}
    for r in direct_relations:
        involved_ids.add(r.source_entity_id)
        involved_ids.add(r.target_entity_id)

    # 1跳扩展：查询直接关联实体的其他关系
    expanded_relations = list(direct_relations)
    if max_hops >= 2:
        extra = (
            db.query(Relation)
            .filter(
                Relation.document_id == document_id,
                Relation.source_entity_id.in_(involved_ids),
                ~Relation.id.in_([r.id for r in direct_relations]),
            )
            .all()
        )
        for r in extra:
            involved_ids.add(r.source_entity_id)
            involved_ids.add(r.target_entity_id)
        expanded_relations.extend(extra)

    # 获取所有涉及的实体详情
    related_entities = (
        db.query(Entity)
        .filter(Entity.id.in_(involved_ids), Entity.id != entity_id)
        .all()
    )

    entity_map = {e.id: e for e in related_entities}
    entity_map[entity.id] = entity

    # 组装关系快照
    relations_out = []
    for r in expanded_relations:
        src = entity_map.get(r.source_entity_id)
        tgt = entity_map.get(r.target_entity_id)
        relations_out.append({
            "source_name": src.name if src else "?",
            "target_name": tgt.name if tgt else "?",
            "relation_type": r.relation_type,
            "description": r.description or "",
        })

    return {
        "entity": {"name": entity.name, "type": entity.entity_type, "description": entity.description},
        "relations": relations_out,
        "related_entities": [
            {"name": e.name, "type": e.entity_type, "description": e.description}
            for e in related_entities
        ],
    }


def format_fact_chain_for_prompt(fact_chain: dict) -> str:
    """将事实链格式化为 LLM 可读的文本。"""
    entity = fact_chain.get("entity")
    if not entity:
        return ""

    lines = [f"目标知识点：{entity['name']}（{entity.get('type', '?')}）"]
    if entity.get("description"):
        lines.append(f"描述：{entity['description']}")
    lines.append("")

    if fact_chain["relations"]:
        lines.append("关联关系：")
        for r in fact_chain["relations"]:
            lines.append(f"  - {r['source_name']} --[{r['relation_type']}]--> {r['target_name']}")
            if r.get("description"):
                lines.append(f"    {r['description']}")
        lines.append("")

    if fact_chain["related_entities"]:
        lines.append("相关实体：")
        for e in fact_chain["related_entities"]:
            lines.append(f"  - {e['name']} ({e.get('type', '?')}): {e.get('description', '')}")

    return "\n".join(lines)


# ── 完整图谱查询 ─────────────────────────────────────────────────────────

def get_full_graph(db: Session, document_id: UUID) -> dict:
    """获取文档的完整图谱（实体 + 关系 + 名称映射）。"""
    entities = get_entities(db, document_id)
    relations = get_relations(db, document_id)

    entity_map = {str(e.id): {"name": e.name, "entity_type": e.entity_type} for e in entities}

    return {
        "document_id": str(document_id),
        "entities": [{"id": str(e.id), "name": e.name, "entity_type": e.entity_type, "description": e.description} for e in entities],
        "relations": [
            {
                "id": str(r.id),
                "source_entity_id": str(r.source_entity_id),
                "target_entity_id": str(r.target_entity_id),
                "source_name": entity_map.get(str(r.source_entity_id), {}).get("name", "?"),
                "target_name": entity_map.get(str(r.target_entity_id), {}).get("name", "?"),
                "relation_type": r.relation_type,
                "description": r.description or "",
            }
            for r in relations
        ],
        "document_title": db.query(Document).filter(Document.id == document_id).value(Document.title),
    }
