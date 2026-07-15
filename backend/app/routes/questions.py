"""
M2.8 出题 API 路由 — 生成 / 列表 / 删除。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.question_generator import generate_questions, save_questions
from app.database import get_db
from app.models import Document, Question
from app.schemas import (
    QuestionGenerateRequest,
    QuestionItem,
    QuestionListResponse,
)

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _run_question_gen_async(document_id: uuid.UUID, entity_ids: list[uuid.UUID] | None, types: list[str] | None, count_per_type: int) -> None:
    """后台生成题目。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning("Question gen: doc %s not found", document_id)
            return

        questions = generate_questions(db, document_id=document_id, entity_ids=entity_ids, types=types, count_per_type=count_per_type)
        if questions:
            save_questions(db, document_id, questions, entity_ids)
            db.commit()
            logger.info("Question gen: %d saved for doc %s", len(questions), document_id)
        else:
            logger.warning("Question gen: no questions generated for doc %s", document_id)
    except Exception:
        logger.warning("Question gen failed", exc_info=True)
    finally:
        db.close()


@router.post("/generate")
def generate_questions_endpoint(
    payload: QuestionGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """异步生成题目：立即返回，后台生成后通过 GET 列表查询结果。"""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    background_tasks.add_task(
        _run_question_gen_async,
        payload.document_id,
        payload.entity_ids,
        payload.types,
        payload.count_per_type,
    )

    return {"status": "started", "document_id": str(payload.document_id)}


@router.get("", response_model=QuestionListResponse)
def list_questions(
    document_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    """获取文档的题目列表。"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    q = db.query(Question).filter(Question.document_id == document_id)

    if entity_id:
        q = q.filter(Question.source_entity_ids.any(entity_id))

    questions = q.order_by(Question.created_at.desc()).all()

    return QuestionListResponse(
        document_id=document_id,
        questions=[
            QuestionItem(
                id=qq.id,
                question_type=qq.question_type,
                stem=qq.stem,
                answer=qq.answer,
                options=qq.options,
                explanation=qq.explanation,
                bloom_level=qq.bloom_level,
                difficulty_estimate=qq.difficulty_estimate,
                source_entity_ids=qq.source_entity_ids,
            )
            for qq in questions
        ],
    )


@router.delete("/{id}", status_code=204)
def delete_question(id: uuid.UUID, db: Session = Depends(get_db)):
    """删除指定题目。"""
    q = db.query(Question).filter(Question.id == id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
