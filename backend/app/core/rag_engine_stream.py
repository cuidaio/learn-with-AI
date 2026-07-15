"""
M2.6 流式 RAG 引擎 — SSE generator。

保留 M2 rag_ask() 的 embed → search → context → LLM 流程，
仅在调用层做流式改造：LLM 调用使用 stream=True，逐 token 输出。
"""

import json
import time
from datetime import datetime
from uuid import UUID

from openai import OpenAI

from app.core.config import settings
from app.core.embeddings import embed_text
from app.core.logging import logger
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
from app.models import Document, SectionBlock, SubChunk


def _distance_to_score(dist: float) -> float:
    return max(0.0, 1.0 - dist)


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def rag_ask_stream(
    db_session,
    document_ids: list[UUID],
    question: str,
    top_k: int = 5,
):
    """流式 RAG 生成器，逐段 yield SSE 编码的字符串。

    SSE events:
      {"type":"start","timestamp":"..."}
      {"type":"token","content":"..."}
      {"type":"done","sources":[...]}
    """
    from app.models import Document, SectionBlock, SubChunk

    t_ask_start = time.monotonic()

    if not document_ids:
        yield _sse("start", {"timestamp": datetime.utcnow().isoformat()})
        yield _sse("done", {"sources": []})
        logger.info("ASK total: %.3fs (empty)", time.monotonic() - t_ask_start)
        return

    # 1. Embedding
    t_embed_start = time.monotonic()
    query_vec = embed_text(question)
    logger.info("Embedding: %.3fs", time.monotonic() - t_embed_start)

    # 2. 向量检索
    t_search_start = time.monotonic()
    distance_expr = SubChunk.embedding.cosine_distance(query_vec)
    results = (
        db_session.query(SubChunk, distance_expr.label("distance"))
        .filter(
            SubChunk.document_id.in_(document_ids),
            SubChunk.embedding.isnot(None),
        )
        .order_by(distance_expr)
        .limit(top_k)
        .all()
    )
    logger.info("Vector search: %.3fs", time.monotonic() - t_search_start)

    if not results:
        logger.info("RAG: no matching sub-chunks found")
        yield _sse("start", {"timestamp": datetime.utcnow().isoformat()})
        yield _sse("done", {"sources": []})
        logger.info("ASK total: %.3fs (no results)", time.monotonic() - t_ask_start)
        return

    # 3. sub_chunk → score
    sc_records = [(sc, _distance_to_score(dist)) for sc, dist in results]

    # 4. 查找 section_blocks
    all_section_blocks = (
        db_session.query(SectionBlock)
        .filter(SectionBlock.document_id.in_(document_ids))
        .all()
    )

    matched_sc_ids = {str(sc.id) for sc, _ in sc_records}
    sb_map = {}
    for sb in all_section_blocks:
        sb_sc_ids = {str(sid) for sid in (sb.sub_chunk_ids or [])}
        if sb_sc_ids & matched_sc_ids:
            sb_map[str(sb.id)] = sb

    # 5. section_block relevance
    sc_to_sb = {}
    for sb_id, sb in sb_map.items():
        for sc_id in (sb.sub_chunk_ids or []):
            sc_to_sb[str(sc_id)] = str(sb_id)

    block_relevance = {}
    for sc, score in sc_records:
        sb_id = sc_to_sb.get(str(sc.id))
        if sb_id:
            prev = block_relevance.get(sb_id, 0.0)
            if score > prev:
                block_relevance[sb_id] = score

    # 6. 排序
    sorted_blocks = sorted(
        block_relevance.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    docs = (
        db_session.query(Document)
        .filter(Document.id.in_(document_ids))
        .all()
    )
    doc_title_map = {d.id: d.title for d in docs}

    MAX_REF_CHARS = 800  # 单段参考资料最大长度，控制 LLM prefill 时间

    ref_parts = []
    sources = []
    for idx, (sb_id, score) in enumerate(sorted_blocks, start=1):
        sb = sb_map[sb_id]
        title = sb.title or f"章节 {sb.block_index}"
        doc_title = doc_title_map.get(sb.document_id, "")
        content = sb.content
        if len(content) > MAX_REF_CHARS:
            content = content[:MAX_REF_CHARS] + "\n…[已截断]"
        ref_parts.append(f"[{idx}] 来源：{title}\n{content}")
        sources.append({
            "document_title": doc_title,
            "section_title": title,
            "relevance_score": round(score, 4),
            "cited_in_answer": False,
        })

    references_text = "\n\n".join(ref_parts)
    user_prompt = build_user_prompt(references_text, question)
    t_context_end = time.monotonic()
    logger.info("Context assembly: %.3fs", t_context_end - t_search_start)

    # 7. Start SSE
    yield _sse("start", {"timestamp": datetime.utcnow().isoformat()})

    # 8. 流式调用 LLM
    client = _get_llm_client()
    t_llm_start = time.monotonic()
    full_answer = ""
    try:
        stream = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                full_answer += token
                yield _sse("token", {"content": token})
    except Exception as e:
        logger.error("LLM streaming call failed: %s", e)
        yield _sse("error", {"message": str(e)})
        return
    logger.info("LLM generation: %.3fs", time.monotonic() - t_llm_start)

    # 9. 标记引用
    for i, source in enumerate(sources):
        idx = i + 1
        if f"【{idx}】" in full_answer:
            source["cited_in_answer"] = True

    yield _sse("done", {"sources": sources})
    logger.info("ASK total: %.3fs", time.monotonic() - t_ask_start)


def _sse(event_type: str, data: dict) -> str:
    """将事件类型和字典编码为 SSE 格式字符串。"""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
