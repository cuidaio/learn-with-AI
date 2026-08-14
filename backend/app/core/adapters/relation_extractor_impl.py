"""
RelationExtractorImpl — RelationExtractor 接口的实现。

包装 app.core.relation_extractor.extract_relations（纯 LLM 调用，不涉及 DB）。
"""

from app.core.interfaces import RelationExtractor
from app.core.relation_extractor import extract_relations as _extract_relations


class RelationExtractorImpl(RelationExtractor):
    """包装 extract_relations 函数。"""

    def extract(self, content: str, entity_names: list[str]) -> list[dict]:
        return _extract_relations(content, entity_names)
