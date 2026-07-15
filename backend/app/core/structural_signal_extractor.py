"""
Stage 2: structure signal extraction.

Detect headings / chapter numbers. No confidence — signals only exist or not.
"""

import re
from dataclasses import dataclass


@dataclass
class StructuralSignal:
    position: int
    level: int         # 1=chapter, 2=section, 3=subsection
    content: str
    source: str        # "markdown_heading" | "chinese_chapter" | "chinese_ordinal" | "numeric_ordinal"


def extract_structural_signals(text: str) -> list[StructuralSignal]:
    if not text:
        return []

    signals: list[StructuralSignal] = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        pos = sum(len(l) + 1 for l in lines[:i])
        stripped = line.strip()
        if not stripped:
            continue

        # Markdown heading: ## title
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            signals.append(StructuralSignal(
                position=pos,
                level=len(m.group(1)),
                content=m.group(2).strip(),
                source="markdown_heading",
            ))
            continue

        # Chinese chapter: 第三章 / 第4章
        m = re.match(r"^第[一二三四五六七八九十百千万\d]+[章节]\s*(.*)$", stripped)
        if m:
            signals.append(StructuralSignal(
                position=pos, level=1, content=stripped,
                source="chinese_chapter",
            ))
            continue

        # Chinese ordinal: 一、 （一） 1）
        m = re.match(r"^[（(]?[一二三四五六七八九十][)）]?[.、]?\s*(.*)$", stripped)
        if m and len(stripped) <= 8:
            signals.append(StructuralSignal(
                position=pos, level=3, content=stripped,
                source="chinese_ordinal",
            ))
            continue

        # Numeric ordinal: 1. 2. 3)
        m = re.match(r"^\d+[.、)）]\s*", stripped)
        if m and len(stripped) <= 10:
            signals.append(StructuralSignal(
                position=pos, level=0, content=stripped,
                source="numeric_ordinal",
            ))
            continue

    return signals
