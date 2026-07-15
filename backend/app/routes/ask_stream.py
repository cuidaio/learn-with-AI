"""
M2.6 流式 RAG 问答路由 — POST /api/ask/stream。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.rag_engine_stream import rag_ask_stream
from app.database import get_db
from app.models import Document
from app.schemas import AskRequest

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask/stream")
def ask_stream(payload: AskRequest, db: Session = Depends(get_db)):
    """流式 RAG 问答：SSE 逐 token 返回 LLM 生成结果。"""
    doc_ids = payload.document_ids if payload.document_ids else (
        [payload.document_id] if payload.document_id else []
    )
    if not doc_ids:
        raise HTTPException(status_code=400, detail="请提供 document_id 或 document_ids")
    doc_ids = [UUID(d) if isinstance(d, str) else d for d in doc_ids]

    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    if len(docs) != len(set(doc_ids)):
        found = {d.id for d in docs}
        missing = [str(d) for d in set(doc_ids) if d not in found]
        raise HTTPException(status_code=404, detail=f"文档未找到: {', '.join(missing)}")

    logger.info(
        "ASK/stream: documents=%s question='%s' top_k=%d",
        [str(d) for d in doc_ids], payload.question[:80], payload.top_k,
    )

    return StreamingResponse(
        rag_ask_stream(db, doc_ids, payload.question, payload.top_k),
        media_type="text/event-stream",
    )
