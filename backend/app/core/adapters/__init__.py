"""M3.3 适配器包 — 接口的现有实现包装。"""

from app.core.adapters.postgres_task_store import PostgresTaskStore
from app.core.adapters.llm_client_impl import LLMClientImpl
from app.core.adapters.embedding_client_impl import EmbeddingClientImpl
from app.core.adapters.question_generator_impl import QuestionGeneratorImpl
from app.core.adapters.entity_extractor_impl import EntityExtractorImpl
from app.core.adapters.relation_extractor_impl import RelationExtractorImpl

__all__ = [
    "PostgresTaskStore",
    "LLMClientImpl",
    "EmbeddingClientImpl",
    "QuestionGeneratorImpl",
    "EntityExtractorImpl",
    "RelationExtractorImpl",
]
