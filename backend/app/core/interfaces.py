"""
M3.3 服务接口定义 — 所有外部依赖的抽象层。

任务类通过构造函数注入这些接口，不直接 import 具体实现。
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID


class TaskStore(ABC):
    """任务持久化存储接口。"""

    @abstractmethod
    def get(self, task_id: UUID) -> Optional[Any]:
        ...

    @abstractmethod
    def list(self, document_id: Optional[UUID] = None) -> list[Any]:
        ...

    @abstractmethod
    def save(self, task_type: str, params: dict, **kwargs) -> Any:
        ...

    @abstractmethod
    def update_status(self, task_id: UUID, status: str) -> None:
        ...

    @abstractmethod
    def update_progress(
        self, task_id: UUID,
        completed_steps: Optional[int] = None,
        description: Optional[str] = None,
    ) -> None:
        ...

    @abstractmethod
    def complete(self, task_id: UUID, result: dict) -> None:
        ...

    @abstractmethod
    def fail(self, task_id: UUID, error_message: str) -> None:
        ...

    @abstractmethod
    def delete(self, task_id: UUID) -> bool:
        ...


class QuestionGenerator(ABC):
    """出题生成器接口。"""

    @abstractmethod
    def generate(
        self,
        document_id: UUID,
        entity_ids: list[UUID],
        config: dict,
    ) -> list[dict]:
        ...


class EntityExtractor(ABC):
    """实体提取器接口。"""

    @abstractmethod
    def extract(self, content: str) -> list[dict]:
        ...

    def extract_from_document(
        self,
        document_id: UUID,
        task_id: Optional[UUID] = None,
    ) -> int:
        """M3.4: 并行提取文档中的实体（可选实现，默认不支持）。

        实现应读取 DB 中的 sub_chunks → 并行 LLM 提取 → 去重 → 存入 DB。
        返回保存的实体数量，0 表示无实体。
        """
        raise NotImplementedError("extract_from_document not implemented")


class RelationExtractor(ABC):
    """关系提取器接口。"""

    @abstractmethod
    def extract(self, content: str, entity_names: list[str]) -> list[dict]:
        ...


class LLMClient(ABC):
    """LLM 客户端接口。"""

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: Optional[int] = None,
        response_format: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        ...


class EmbeddingClient(ABC):
    """Embedding 客户端接口。"""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class TaskFactory(ABC):
    """任务工厂接口 — 创建依赖注入就绪的任务实例。"""

    @abstractmethod
    def create(
        self,
        task_type: str,
        task_id: UUID,
        document_id: UUID,
        params: dict,
    ) -> Any:
        ...
