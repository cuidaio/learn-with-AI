"""
EntityExtractorImpl — EntityExtractor 接口的实现。

包装 app.core.entity_extractor 的同步 extract_entities 和异步并行提取。
"""

import asyncio
from typing import Optional
from uuid import UUID

from app.core.entity_extractor import extract_entities as _extract_entities
from app.core.interfaces import EntityExtractor


class EntityExtractorImpl(EntityExtractor):
    """实体提取器适配器。

    同步 extract() 向后兼容；
    extract_from_document() 使用 M3.4 并行流水线。
    """

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers

    def extract(self, content: str) -> list[dict]:
        """同步单次提取（向后兼容）。"""
        return _extract_entities(content)

    def extract_from_document(
        self,
        document_id: UUID,
        task_id: Optional[UUID] = None,
    ) -> int:
        """同步包装：在任务线程中跑一次 asyncio 事件循环。

        内部使用 ParallelEntityExtractor 实现并行分块提取 + 去重。
        返回保存的实体数量。
        """
        from app.core.entity_extractor import ParallelEntityExtractor

        extractor = ParallelEntityExtractor(max_workers=self.max_workers)
        return asyncio.run(extractor.extract_from_document(document_id, task_id))
