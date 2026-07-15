"""
M2 检索与问答引擎。

流程：
1. 向量检索命中 sub_chunks（pgvector cosine）
2. 聚合所属 section_blocks
3. 按相关性排序组装 Prompt
4. 调用 LLM 生成回答
"""

import time
from uuid import UUID

from openai import OpenAI

from app.core.config import settings
from app.core.embeddings import embed_text
from app.core.logging import logger

_client: OpenAI | None = None


def _get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


def _distance_to_score(dist: float) -> float:
    """将 pgvector cosine_distance（0~2）转为相关度分数（0~1）。"""
    return max(0.0, 1.0 - dist)


def rag_ask(
    db_session,
    document_ids: list[UUID],
    question: str,
    top_k: int = 5,
) -> dict:
    """RAG 问答主流程（支持多文档检索）。

    Args:
        document_ids: 文档 UUID 列表，至少一个。
        question: 用户问题。
        top_k: 从全部文档中取 top_k 个最相关子块。

    Returns:
        dict with keys "answer" (str) and "sources" (list[dict]).
    """
    from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
    from app.models import Document, SectionBlock, SubChunk

    t_ask_start = time.monotonic()
    logger.info("ASK start")

    if not document_ids:
        return {"answer": "教材中未涉及该内容", "sources": []}

    # 1. 嵌入问题
    t_embed_start = time.monotonic()
    query_vec = embed_text(question)
    logger.info("Embedding: %.3fs", time.monotonic() - t_embed_start)
    logger.info(
        "RAG: question embedded, querying top-%d sub-chunks across %d documents",
        top_k, len(document_ids),
    )

    # 2. 向量检索 sub_chunks（跨文档一次查询）
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
        return {"answer": "教材中未涉及该内容", "sources": []}

    # 3. 构建 sub_chunk → 相似度映射
    sc_records: list[tuple[SubChunk, float]] = []
    for sc, dist in results:
        score = _distance_to_score(dist)
        sc_records.append((sc, score))

    # 4. 查找这些 sub_chunk 所属的 section_blocks（跨文档）
    all_section_blocks = (
        db_session.query(SectionBlock)
        .filter(SectionBlock.document_id.in_(document_ids))
        .all()
    )

    matched_sc_ids = {str(sc.id) for sc, _ in sc_records}
    sb_map: dict[str, SectionBlock] = {}
    for sb in all_section_blocks:
        sb_sc_ids = {str(sid) for sid in (sb.sub_chunk_ids or [])}
        if sb_sc_ids & matched_sc_ids:
            sb_map[str(sb.id)] = sb

    # 5. 计算每个 section_block 的 relevance = 所含子块的最大相关度
    sc_to_sb: dict[str, str] = {}
    for sb_id, sb in sb_map.items():
        for sc_id in (sb.sub_chunk_ids or []):
            sc_to_sb[str(sc_id)] = str(sb_id)

    block_relevance: dict[str, float] = {}
    for sc, score in sc_records:
        sb_id = sc_to_sb.get(str(sc.id))
        if sb_id:
            prev = block_relevance.get(sb_id, 0.0)
            if score > prev:
                block_relevance[sb_id] = score

    # 6. 构建按相关度降序排列的参考资料
    sorted_blocks = sorted(
        block_relevance.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    # 获取所有涉及文档的标题
    docs = (
        db_session.query(Document)
        .filter(Document.id.in_(document_ids))
        .all()
    )
    doc_title_map: dict[UUID, str] = {d.id: d.title for d in docs}

    MAX_REF_CHARS = 800  # 单段参考资料最大长度，控制 LLM prefill 时间

    ref_parts: list[str] = []
    sources: list[dict] = []
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

    # 7. 组装 Prompt（参考资料在前，问题在后）
    user_prompt = build_user_prompt(references_text, question)
    t_context_end = time.monotonic()
    logger.info("Context assembly: %.3fs", t_context_end - t_search_start)

    # 8. 调用 LLM
    client = _get_llm_client()
    t_llm_start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        answer = response.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM API call failed: %s", e)
        raise
    logger.info("LLM generation: %.3fs", time.monotonic() - t_llm_start)

    # 9. 标记被引用的来源
    for i, source in enumerate(sources):
        idx = i + 1
        if f"【{idx}】" in answer:
            source["cited_in_answer"] = True

    logger.info("ASK total: %.3fs", time.monotonic() - t_ask_start)
    return {"answer": answer, "sources": sources}
