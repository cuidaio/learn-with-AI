"""
M3: 实体高亮 — 在文档原文中标记实体名词。
"""

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.graph_store import get_entities


def highlight_entities(
    db: Session,
    document_id: UUID,
    text: str,
) -> list[dict]:
    """在原文中查找实体并返回标记位置列表。

    Returns:
        [{"entity_name", "entity_type", "start", "end"}, ...]
        按 start 位置升序排列，不重叠。
    """
    entities = get_entities(db, document_id)
    if not entities:
        return []

    # 按名称长度降序排列，避免短名匹配长名的一部分
    entities_sorted = sorted(entities, key=lambda e: len(e.name or ""), reverse=True)

    highlights: list[dict] = []
    seen_ranges: list[tuple[int, int]] = []  # (start, end) 已佔用区间

    for entity in entities_sorted:
        name = entity.name
        if not name:
            continue

        # 对整个原文查找所有出现位置（不重叠）
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()

            # 检查是否已被更长实体覆盖
            if any(s < end and e > start for s, e in seen_ranges):
                continue

            highlights.append({
                "entity_name": name,
                "entity_type": entity.entity_type or "concept",
                "start": start,
                "end": end,
            })
            seen_ranges.append((start, end))

    # 按 start 升序
    highlights.sort(key=lambda h: h["start"])
    return highlights
