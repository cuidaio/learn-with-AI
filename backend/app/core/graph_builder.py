"""
M2.8 图谱构建编排器 — 文档上传后异步执行实体提取 + 关系提取 + 存储。
"""

import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.entity_extractor import extract_entities
from app.core.graph_store import (
    delete_entities_by_document,
    delete_relations_by_document,
    get_entities,
    save_entities,
    save_relations,
)
from app.core.logging import logger
from app.core.relation_extractor import extract_relations
from app.models import Document, SectionBlock


def _aggregate_content(db: Session, document_id: UUID) -> str | None:
    """聚合文档内容，返回纯文本或 None（无内容时）。"""
    sections = (
        db.query(SectionBlock)
        .filter(SectionBlock.document_id == document_id)
        .order_by(SectionBlock.block_index)
        .all()
    )
    if not sections:
        return None
    max_sections = settings.graph_extraction_batch_size or 10
    aggregated = "\n\n".join(sb.content for sb in sections[:max_sections])
    if len(aggregated) > 12000:
        aggregated = aggregated[:12000] + "\n…[已截断]"
    return aggregated


def extract_and_save_entities(db: Session, document_id: UUID) -> bool:
    """阶段1：实体提取 → 立即提交，前端可见。

    Returns: True 有实体，False 无实体。
    """
    from datetime import datetime

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return False

    delete_entities_by_document(db, document_id)
    delete_relations_by_document(db, document_id)

    aggregated = _aggregate_content(db, document_id)
    if not aggregated:
        doc.lifecycle_status = "unchanged"
        doc.processed_at = None
        db.commit()
        return False

    entities = extract_entities(aggregated)
    if not entities:
        logger.warning("Graph: no entities extracted for doc %s", document_id)
        doc.lifecycle_status = "unchanged"
        doc.processed_at = None
        db.commit()
        return False

    entities = entities[: settings.graph_max_entities_per_doc]
    save_entities(db, document_id, entities)
    doc.lifecycle_status = "unchanged"
    doc.processed_at = datetime.utcnow()
    db.commit()
    logger.info("Graph: %d entities saved for doc %s", len(entities), document_id)
    return True


def extract_and_save_relations(db: Session, document_id: UUID) -> None:
    """阶段2：关系提取（实体已存在时调用）。"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return

    aggregated = _aggregate_content(db, document_id)
    if not aggregated:
        return

    from app.models import Entity
    entities = db.query(Entity).filter(Entity.document_id == document_id).all()
    if not entities:
        return

    entity_names = [e.name for e in entities]
    relations = extract_relations(aggregated, entity_names)
    relations = relations[: settings.graph_max_relations_per_doc]

    name_to_id = {e.name: e.id for e in entities}
    if relations:
        save_relations(db, document_id, relations, name_to_id)

    db.commit()
    logger.info("Graph: %d relations saved for doc %s", len(relations), document_id)
