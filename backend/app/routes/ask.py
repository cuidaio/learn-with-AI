"""
M2.5 RAG 问答路由 — POST /api/ask（支持多文档）。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.rag_engine import rag_ask
from app.database import get_db
from app.models import Document
from app.schemas import AskRequest, AskResponse, SourceItem

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest, db: Session = Depends(get_db)):
    """RAG 问答（支持多文档）：检索相关子块 → 聚合章节块 → LLM 生成带引用的回答。"""
    # 解析文档 ID（document_ids 优先，兼容单文档 document_id）
    doc_ids = payload.document_ids if payload.document_ids else (
        [payload.document_id] if payload.document_id else []
    )
    if not doc_ids:
        raise HTTPException(status_code=400, detail="请提供 document_id 或 document_ids")
    doc_ids = [UUID(d) if isinstance(d, str) else d for d in doc_ids]

    # 验证所有文档存在
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    if len(docs) != len(set(doc_ids)):
        found = {d.id for d in docs}
        missing = [str(d) for d in set(doc_ids) if d not in found]
        raise HTTPException(status_code=404, detail=f"文档未找到: {', '.join(missing)}")

    logger.info(
        "ASK: documents=%s question='%s' top_k=%d",
        [str(d) for d in doc_ids], payload.question[:80], payload.top_k,
    )

    try:
        result = rag_ask(
            db_session=db,
            document_ids=doc_ids,
            question=payload.question,
            top_k=payload.top_k,
        )
    except Exception as e:
        logger.error("RAG ask failed: %s", e)
        raise HTTPException(status_code=503, detail=f"RAG engine error: {str(e)}")

    return AskResponse(
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
    )
