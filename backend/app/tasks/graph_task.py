"""
M3.2 知识图谱任务 — 包装现有 graph_builder 逻辑。
M3.3: 通过构造函数注入 EntityExtractor + RelationExtractor，不直接 import。
"""

from typing import Any, Optional
from uuid import UUID

from app.core.interfaces import EntityExtractor, RelationExtractor
from app.tasks.base import BaseTask
from app.tasks.registry import register_task


@register_task
class EntityExtractionTask(BaseTask):
    """实体提取任务（文档导入时自动创建）。"""
    task_type = "entity_extraction"
    display_name = "实体提取"
    icon = "🏷️"
    description = "从文档中提取实体和关系"
    timeout_seconds = 600

    def __init__(
        self,
        task_id: UUID,
        params: dict,
        entity_extractor: Optional[EntityExtractor] = None,
        relation_extractor: Optional[RelationExtractor] = None,
    ):
        super().__init__(task_id, params)
        self._entity_extractor = entity_extractor
        self._relation_extractor = relation_extractor

    def execute(self) -> None:
        """执行实体提取任务。

        如果注入了 extractor，使用注入的实例；
        否则降级为 import 现有 execute_entity_extraction_task。
        """
        if self._entity_extractor is not None:
            self._execute_with_di()
        else:
            from app.core.graph_builder import execute_entity_extraction_task

            doc_id = UUID(self.params["document_id"])
            doc_title = self.params.get("title", self.display_name)
            execute_entity_extraction_task(self.task_id, doc_id, doc_title)

    def _execute_with_di(self) -> None:
        """使用注入的 EntityExtractor（M3.4 并行提取） + RelationExtractor 执行。"""
        from app.database import SessionLocal
        from app.core.graph_builder import extract_and_save_relations
        from app.core.task_manager import (
            complete_task,
            fail_task,
        )

        db = SessionLocal()
        try:
            doc_id = UUID(self.params["document_id"])
            doc_title = self.params.get("title", self.display_name)

            # M3.4: 并行提取（extract_from_document 管理自己的 session、进度、去重）
            entity_count = self._entity_extractor.extract_from_document(doc_id, self.task_id)
            has = entity_count > 0

            if has:
                try:
                    extract_and_save_relations(db, doc_id)
                except Exception as rel_err:
                    from app.core.logging import logger
                    logger.warning(
                        "Relation extraction failed for doc %s: %s",
                        doc_id, rel_err,
                    )
                    db.rollback()

                from app.models import Entity
                entities = (
                    db.query(Entity).filter(Entity.document_id == doc_id).all()
                )
                entity_list = [
                    {
                        "id": str(e.id),
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "description": e.description,
                    }
                    for e in entities
                ]
                complete_task(db, self.task_id, {
                    "content_type": "entities",
                    "title": f"{doc_title} 实体一览",
                    "data": entity_list,
                })
            else:
                fail_task(db, self.task_id, "未提取到任何实体")
            db.commit()
        except Exception as e:
            from app.core.logging import logger
            logger.error(
                "Entity extraction task %s failed: %s",
                self.task_id, e, exc_info=True,
            )
            try:
                fail_task(db, self.task_id, str(e))
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def get_card_fields(self) -> dict:
        return {
            "card_title": self.display_name,
            "card_icon": self.icon,
            "result_content_type": "entities",
            "total_steps": 1,
        }


@register_task
class GraphTask(BaseTask):
    """知识图谱构建任务（显式创建的图谱任务）。"""
    task_type = "graph_generation"
    display_name = "知识图谱"
    icon = "📊"
    description = "构建文档的知识图谱（实体 + 关系）"
    timeout_seconds = 600

    def __init__(
        self,
        task_id: UUID,
        params: dict,
        entity_extractor: Optional[EntityExtractor] = None,
        relation_extractor: Optional[RelationExtractor] = None,
    ):
        super().__init__(task_id, params)
        self._entity_extractor = entity_extractor
        self._relation_extractor = relation_extractor

    def execute(self) -> None:
        """执行知识图谱构建任务（实体提取 + 关系提取 + 图数据组装）。"""
        from app.database import SessionLocal
        from app.core.graph_store import get_full_graph
        from app.core.graph_builder import (
            extract_and_save_entities,
            extract_and_save_relations,
        )
        from app.core.task_manager import (
            complete_task,
            fail_task,
            update_task_progress,
            update_task_status,
        )

        db = SessionLocal()
        try:
            doc_id = UUID(self.params["document_id"])
            update_task_status(db, self.task_id, "running")
            update_task_progress(db, self.task_id, 0, "开始实体提取")
            db.commit()

            from app.models import Entity

            existing = db.query(Entity).filter(Entity.document_id == doc_id).count()
            if existing > 0:
                update_task_progress(db, self.task_id, 0, "实体已存在，直接关系提取")
                db.commit()
            else:
                update_task_progress(db, self.task_id, 0, "开始实体提取")
                db.commit()
                has = extract_and_save_entities(db, doc_id)
                if not has:
                    fail_task(db, self.task_id, "实体提取失败：未提取到任何实体")
                    db.commit()
                    return
                update_task_progress(db, self.task_id, 1, "实体提取完成，开始关系提取")
                db.commit()

            extract_and_save_relations(db, doc_id)

            from app.models import Task as TaskModel

            doc_title = (
                db.query(TaskModel.card_title)
                .filter(TaskModel.id == self.task_id)
                .scalar()
                or "知识图谱"
            )
            graph = get_full_graph(db, doc_id)
            complete_task(db, self.task_id, {
                "content_type": "knowledge_graph",
                "title": doc_title,
                "data": graph,
            })
            db.commit()
        except Exception as e:
            from app.core.logging import logger
            logger.error(
                "Graph task %s failed: %s", self.task_id, e, exc_info=True,
            )
            try:
                fail_task(db, self.task_id, str(e))
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def get_card_fields(self) -> dict:
        return {
            "card_title": self.display_name,
            "card_icon": self.icon,
            "result_content_type": "knowledge_graph",
            "total_steps": 2,
        }
