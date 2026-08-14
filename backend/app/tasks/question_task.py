"""
M3.2 出题任务 — 包装现有 question_generator 逻辑。
M3.3: 通过构造函数注入 QuestionGenerator + LLMClient，不直接 import。
"""

from typing import Any, Optional
from uuid import UUID

from app.core.interfaces import LLMClient, QuestionGenerator
from app.tasks.base import BaseTask
from app.tasks.registry import register_task


@register_task
class QuestionTask(BaseTask):
    task_type = "question_generation"
    display_name = "出题"
    icon = "📝"
    description = "基于选中的知识点生成训练题目"
    timeout_seconds = 600

    def __init__(
        self,
        task_id: UUID,
        params: dict,
        question_generator: Optional[QuestionGenerator] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(task_id, params)
        self._question_generator = question_generator
        self._llm_client = llm_client

    def execute(self) -> None:
        """执行出题任务。

        如果注入了 question_generator，使用注入的实例；
        否则降级为 import 现有 execute_question_task。
        """
        if self._question_generator is not None:
            self._execute_with_di()
        else:
            from app.core.question_generator import execute_question_task

            execute_question_task(self.task_id, self.params)

    def _execute_with_di(self) -> None:
        """使用注入的 QuestionGenerator 执行。"""
        from app.database import SessionLocal
        from app.core.task_manager import (
            complete_task,
            fail_task,
            update_task_progress,
            update_task_status,
        )

        db = SessionLocal()
        try:
            update_task_status(db, self.task_id, "running")
            update_task_progress(db, self.task_id, 0, "开始出题")
            db.commit()

            doc_id = UUID(self.params["document_id"])
            entity_ids = [
                UUID(e) if isinstance(e, str) else e
                for e in self.params.get("entity_ids", [])
            ]

            questions = self._question_generator.generate(
                document_id=doc_id,
                entity_ids=entity_ids if entity_ids else [],
                config=self.params,
            )

            if not questions:
                fail_task(db, self.task_id, "出题失败：未生成任何题目")
                db.commit()
                return

            from app.core.question_generator import save_questions

            saved = save_questions(db, doc_id, questions, entity_ids)

            types_breakdown: dict[str, int] = {}
            for q in questions:
                t = q["question_type"]
                types_breakdown[t] = types_breakdown.get(t, 0) + 1

            from app.models import Document as DocModel

            doc_title = (
                db.query(DocModel.title)
                .filter(DocModel.id == doc_id)
                .scalar()
                or "文档"
            )

            complete_task(db, self.task_id, {
                "content_type": "questions",
                "title": f"{doc_title} 训练题",
                "data": {
                    "questions": questions,
                    "metadata": {
                        "total_generated": len(questions),
                        "saved_to_db": saved,
                        "types_breakdown": types_breakdown,
                    },
                },
            })
            db.commit()
        except Exception as e:
            from app.core.logging import logger
            logger.error(
                "Question task %s failed: %s", self.task_id, e, exc_info=True
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
            "result_content_type": "questions",
            "total_steps": None,
        }
