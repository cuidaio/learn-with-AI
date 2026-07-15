"""
Stage 3: atomic unit split.

Split by paragraph (\n\n). Long paragraphs (> paragraph_split_chars)
further split by sentence. Mark is_signal_boundary=True for units
containing structure signal positions.
"""

import re
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class AtomicUnit:
    content: str
    start_pos: int
    end_pos: int
    type: str            # "heading" | "paragraph" | "sentence"
    heading_level: int = 0
    is_signal_boundary: bool = False


# ---------------------------------------------------------------------------
# Sentence split
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；\n])", text)
    sentences = [p.strip() for p in parts if p.strip()]
    if len(sentences) <= 1 and len(text) > 20:
        parts = re.split(r"(?<=[，、])", text)
        sentences = [p.strip() for p in parts if p.strip()]
    if len(sentences) <= 1 and len(text) > 20:
        sentences = [text[i:i+100].strip() for i in range(0, len(text), 100) if text[i:i+100].strip()]
    return sentences if sentences else [text.strip()]


# ---------------------------------------------------------------------------
# Paragraph split
# ---------------------------------------------------------------------------


def _split_paragraph(text: str) -> list[tuple[str, int, int]]:
    """Split by blank line. Returns [(content, start, end)]."""
    results: list[tuple[str, int, int]] = []
    last_end = 0
    for m in re.finditer(r"\n\s*\n", text):
        chunk = text[last_end:m.start()].strip()
        if chunk:
            results.append((chunk, last_end, m.start()))
        last_end = m.end()
    chunk = text[last_end:].strip()
    if chunk:
        results.append((chunk, last_end, len(text)))
    return results


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def split_atomic_units(text: str, signals: list) -> list[AtomicUnit]:
    if not text:
        return []

    signal_positions: set[int] = {s.position for s in signals}
    signal_levels: dict[int, int] = {s.position: s.level for s in signals}
    units: list[AtomicUnit] = []

    for content, para_start, para_end in _split_paragraph(text):
        if not content:
            continue

        para_has_signal = any(sp >= para_start and sp < para_end for sp in signal_positions)
        is_single_line = "\n" not in content

        if para_has_signal and is_single_line and len(content) <= 100:
            # Single-line heading matching a signal
            sig_pos = next(sp for sp in signal_positions if para_start <= sp < para_end)
            units.append(AtomicUnit(
                content=content,
                start_pos=para_start,
                end_pos=para_end,
                type="heading",
                heading_level=signal_levels.get(sig_pos, 0),
                is_signal_boundary=True,
            ))
        elif len(content) > settings.paragraph_split_chars:
            # Long paragraph → split by sentence
            cursor = para_start
            for sent in _split_sentences(content):
                s_start = text.find(sent, cursor)
                if s_start < 0:
                    s_start = cursor
                s_end = s_start + len(sent)
                sent_is_signal = any(sp >= s_start and sp < s_end for sp in signal_positions)
                units.append(AtomicUnit(
                    content=sent,
                    start_pos=s_start,
                    end_pos=s_end,
                    type="sentence",
                    is_signal_boundary=sent_is_signal,
                ))
                cursor = s_end
        else:
            # Normal paragraph
            units.append(AtomicUnit(
                content=content,
                start_pos=para_start,
                end_pos=para_end,
                type="paragraph",
                is_signal_boundary=para_has_signal,
            ))

    return units