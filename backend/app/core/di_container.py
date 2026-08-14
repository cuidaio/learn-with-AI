"""
M3.3 依赖注入容器 — 组装所有外部依赖。

单例容器，在 main.py lifespan 中初始化。
"""

from app.core.config import settings
from app.core.interfaces import (
    EmbeddingClient,
    EntityExtractor,
    LLMClient,
    QuestionGenerator,
    RelationExtractor,
    TaskFactory,
    TaskStore,
)


class DIContainer:
    """依赖注入容器，管理所有服务实例（懒加载单例）。"""

    def __init__(self):
        self._singletons: dict[str, object] = {}

    # ── LLM ─────────────────────────────────────────────────────

    def get_llm_client(self) -> LLMClient:
        if "llm_client" not in self._singletons:
            from app.core.adapters import LLMClientImpl

            self._singletons["llm_client"] = LLMClientImpl(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        return self._singletons["llm_client"]  # type: ignore[return-value]

    # ── Embedding ───────────────────────────────────────────────

    def get_embedding_client(self) -> EmbeddingClient:
        if "embedding_client" not in self._singletons:
            from app.core.adapters import EmbeddingClientImpl

            self._singletons["embedding_client"] = EmbeddingClientImpl()
        return self._singletons["embedding_client"]  # type: ignore[return-value]

    # ── 出题 ────────────────────────────────────────────────────

    def get_question_generator(self) -> QuestionGenerator:
        if "question_generator" not in self._singletons:
            from app.core.adapters import QuestionGeneratorImpl

            self._singletons["question_generator"] = QuestionGeneratorImpl(
                llm_client=self.get_llm_client(),
                embedding_client=self.get_embedding_client(),
            )
        return self._singletons["question_generator"]  # type: ignore[return-value]

    # ── 实体提取 ────────────────────────────────────────────────

    def get_entity_extractor(self) -> EntityExtractor:
        if "entity_extractor" not in self._singletons:
            from app.core.adapters import EntityExtractorImpl

            self._singletons["entity_extractor"] = EntityExtractorImpl(
                max_workers=settings.entity_extraction_workers,
            )
        return self._singletons["entity_extractor"]  # type: ignore[return-value]

    # ── 关系提取 ────────────────────────────────────────────────

    def get_relation_extractor(self) -> RelationExtractor:
        if "relation_extractor" not in self._singletons:
            from app.core.adapters import RelationExtractorImpl

            self._singletons["relation_extractor"] = RelationExtractorImpl()
        return self._singletons["relation_extractor"]  # type: ignore[return-value]

    # ── 任务存储 ────────────────────────────────────────────────

    def get_task_store(self) -> TaskStore:
        if "task_store" not in self._singletons:
            from app.core.adapters import PostgresTaskStore

            self._singletons["task_store"] = PostgresTaskStore()
        return self._singletons["task_store"]  # type: ignore[return-value]

    # ── 任务工厂 ────────────────────────────────────────────────

    def get_task_factory(self) -> TaskFactory:
        if "task_factory" not in self._singletons:
            from app.tasks.registry import RegistryBasedTaskFactory

            self._singletons["task_factory"] = RegistryBasedTaskFactory(
                question_generator=self.get_question_generator(),
                entity_extractor=self.get_entity_extractor(),
                relation_extractor=self.get_relation_extractor(),
                llm_client=self.get_llm_client(),
            )
        return self._singletons["task_factory"]  # type: ignore[return-value]

    # ── TaskManager ────────────────────────────────────────────

    def get_task_manager(self):
        if "task_manager" not in self._singletons:
            from app.core.task_manager import TaskManager

            self._singletons["task_manager"] = TaskManager(
                task_store=self.get_task_store(),
                task_factory=self.get_task_factory(),
            )
        return self._singletons["task_manager"]


# ── 全局单例 ──────────────────────────────────────────────────────

_container: DIContainer | None = None


def get_container() -> DIContainer:
    """获取全局 DI 容器。"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def init_container() -> DIContainer:
    """初始化全局 DI 容器（在 app lifespan 中调用）。"""
    global _container
    _container = DIContainer()
    return _container
