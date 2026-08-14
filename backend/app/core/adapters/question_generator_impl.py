"""
QuestionGeneratorImpl — QuestionGenerator 接口的现有实现包装。

包装 app.core.question_generator.generate_questions（同步版本）。
"""

from uuid import UUID

from app.core.interfaces import (
    EmbeddingClient,
    LLMClient,
    QuestionGenerator,
)


class QuestionGeneratorImpl(QuestionGenerator):
    """将现有出题逻辑包装为 QuestionGenerator 接口。"""

    def __init__(
        self,
        llm_client: LLMClient,
        embedding_client: EmbeddingClient,
    ):
        self._llm = llm_client
        self._embedding = embedding_client

    def generate(
        self,
        document_id: UUID,
        entity_ids: list[UUID],
        config: dict,
    ) -> list[dict]:
        from app.core.question_generator import generate_questions
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            results = generate_questions(
                db,
                document_id=document_id,
                entity_ids=entity_ids if entity_ids else None,
                types=config.get("types"),
                count_per_type=config.get("count_per_type", 3),
            )
            db.commit()
            return results
        finally:
            db.close()
