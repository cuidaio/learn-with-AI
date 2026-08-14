"""
M3: 学习事件埋点 API。
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LearningEvent
from app.schemas import LearningEventCreate, LearningEventResponse

router = APIRouter(prefix="/api/learning-events", tags=["learning_events"])


@router.post("", response_model=LearningEventResponse, status_code=201)
def create_event(payload: LearningEventCreate, db: Session = Depends(get_db)):
    event = LearningEvent(
        id=uuid.uuid4(),
        event_type=payload.event_type,
        document_id=payload.document_id,
        entity_id=payload.entity_id,
        question_id=payload.question_id,
        context=payload.context or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return LearningEventResponse(
        id=event.id,
        event_type=event.event_type,
        document_id=event.document_id,
        entity_id=event.entity_id,
        question_id=event.question_id,
        context=event.context,
        created_at=event.created_at,
    )


@router.post("/batch", status_code=201)
def create_events_batch(payload: list[LearningEventCreate], db: Session = Depends(get_db)):
    events = []
    for item in payload:
        event = LearningEvent(
            id=uuid.uuid4(),
            event_type=item.event_type,
            document_id=item.document_id,
            entity_id=item.entity_id,
            question_id=item.question_id,
            context=item.context or {},
        )
        db.add(event)
        events.append(event)
    db.commit()
    return {"created": len(events)}
