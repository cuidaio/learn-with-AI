"""
Stage 5: section-block builder (SectionBlock / L1).

Rules (priority order):
1. HARD WALL — cut at every StructuralSignal position.
   The SubChunk containing the signal starts the new block.
2. SOFT SIZE — try to keep within section_min_chars ~ section_max_chars.
   Do NOT force-cut at max; avoid breaking semantic integrity.
3. REMAINDER — merge final block into previous if below section_min_chars.
"""

import uuid
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class SectionBlock:
    id: str
    sub_chunk_indices: list[int]
    content: str
    start_pos: int
    end_pos: int
    block_index: int
    title: str | None
    metadata: dict


def build_section_blocks(sub_chunks: list, signals: list) -> list[SectionBlock]:
    if not sub_chunks:
        return []

    # ── 1. Map signal positions to sub-chunk indices ──────
    # A signal sub-chunk starts a new block (except the very first one)
    signal_sc_indices: set[int] = set()
    for sig in signals:
        for i, sc in enumerate(sub_chunks):
            if sc.start_pos <= sig.position < sc.end_pos:
                if sig.position > 0 or i > 0:
                    signal_sc_indices.add(i)
                break

    # ── 2. First pass: cut at signal boundaries ───────────
    raw_groups: list[list[int]] = []
    current: list[int] = []
    for i in range(len(sub_chunks)):
        if i in signal_sc_indices and current:
            raw_groups.append(current)
            current = []
        current.append(i)
    if current:
        raw_groups.append(current)

    # ── 3. Second pass: remainder merge ───────────────────
    blocks: list[SectionBlock] = []

    for group_indices in raw_groups:
        scs = [sub_chunks[i] for i in group_indices]
        total_len = sum(len(sc.content) for sc in scs)
        content = "\n".join(sc.content for sc in scs)

        # Title: find signal at the start of this group
        title = None
        for sig in signals:
            if scs[0].start_pos <= sig.position < scs[0].end_pos:
                title = sig.content
                break

        block = SectionBlock(
            id=str(uuid.uuid4()),
            sub_chunk_indices=group_indices,
            content=content,
            start_pos=scs[0].start_pos,
            end_pos=scs[-1].end_pos,
            block_index=len(blocks),
            title=title,
            metadata={
                "signal_count": sum(1 for i in group_indices if i in signal_sc_indices),
                "char_count": total_len,
            },
        )

        # Merge small block into previous (soft max: 1.5× section_max_chars)
        if blocks and total_len < settings.section_min_chars:
            prev = blocks[-1]
            merged_len = len(prev.content) + 1 + total_len
            if merged_len <= int(settings.section_max_chars * 1.5):
                blocks[-1] = SectionBlock(
                    id=prev.id,
                    sub_chunk_indices=prev.sub_chunk_indices + group_indices,
                    content=prev.content + "\n" + content,
                    start_pos=prev.start_pos,
                    end_pos=scs[-1].end_pos,
                    block_index=prev.block_index,
                    title=prev.title,
                    metadata={
                        "signal_count": prev.metadata.get("signal_count", 0)
                                        + block.metadata.get("signal_count", 0),
                        "char_count": len(prev.content) + 1 + total_len,
                    },
                )
                continue

        blocks.append(block)

    for i, b in enumerate(blocks):
        b.block_index = i

    return blocks