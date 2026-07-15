"""
Stage 4: sub-chunk building (SubChunk / L2).

Accumulate atomic units into sub-chunks. Target 200-1500 char range.
Cuts only at atomic unit boundaries — never mid-sentence.
"""

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class SubChunk:
    content: str
    start_pos: int
    end_pos: int
    chunk_index: int
    source: str           # "heading" | "paragraph" | "sentence" | "merged"


def build_sub_chunks(units: list) -> list[SubChunk]:
    if not units:
        return []

    chunk_size = settings.chunk_size         # 800
    min_size = settings.min_chunk_size       # 200
    max_size = settings.max_chunk_size       # 1500

    chunks: list[SubChunk] = []
    buf: list = []
    buf_len: int = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        content = "\n".join(u.content for u in buf)
        chunks.append(SubChunk(
            content=content,
            start_pos=buf[0].start_pos,
            end_pos=buf[-1].end_pos,
            chunk_index=len(chunks),
            source="merged",
        ))
        buf = []
        buf_len = 0

    for unit in units:
        u_len = len(unit.content)

        # Single unit larger than max_size (rare — atomic units ≤ 300 chars)
        if not buf and u_len > max_size:
            for i in range(0, u_len, max_size):
                piece = unit.content[i:i + max_size]
                chunks.append(SubChunk(
                    content=piece,
                    start_pos=unit.start_pos + i,
                    end_pos=unit.start_pos + min(i + max_size, u_len),
                    chunk_index=len(chunks),
                    source="split",
                ))
            continue

        # Adding this unit would exceed max_size → flush first
        if buf and buf_len + u_len > max_size:
            flush()

        # Signal boundary: flush current sub-chunk, heading starts new one
        # (unconditional — even tiny buffer flushes, so heading never trapped)
        if unit.is_signal_boundary and buf:
            flush()

        buf.append(unit)
        buf_len += u_len

        # Size-based cut at target chunk_size (soft — aims for ~800 chars)
        if buf_len >= chunk_size:
            flush()

    # Flush remainder
    if buf:
        if chunks and buf_len < min_size:
            prev = chunks[-1]
            merged = prev.content + "\n" + "\n".join(u.content for u in buf)
            if len(merged) <= max_size:
                chunks[-1] = SubChunk(
                    content=merged,
                    start_pos=prev.start_pos,
                    end_pos=buf[-1].end_pos,
                    chunk_index=prev.chunk_index,
                    source="merged",
                )
                return chunks
        flush()

    return chunks