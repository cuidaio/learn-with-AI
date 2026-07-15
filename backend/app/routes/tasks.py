"""
M2.8.2 任务 API 路由 — 异步出题任务创建 / 状态查询 / 结果获取。
"""

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.task_manager import get_task, get_tasks
from app.database import get_db
from app.models import Document, Entity, Task
from app.schemas import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskItem,
    TaskListResponse,
    TaskResultResponse,
    TaskStatusResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/questions", response_model=TaskCreateResponse, status_code=201)
def create_question_task(
    payload: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """创建出题任务，立即返回 task_id。后台异步执行。"""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not payload.entity_ids:
        raise HTTPException(status_code=400, detail="entity_ids is required")

    # 校验 entity_ids 全部属于该文档
    existing = (
        db.query(Entity.id)
        .filter(Entity.id.in_(payload.entity_ids), Entity.document_id == payload.document_id)
        .count()
    )
    if existing != len(payload.entity_ids):
        raise HTTPException(status_code=400, detail="Some entity_ids not found in document")

    from app.core.task_manager import create_task
    # model_dump() 返回含 UUID 对象的 dict，JSONB 无法序列化，需转字符串
    raw_params = payload.model_dump()
    serializable_params = json.loads(json.dumps(raw_params, default=str))
    task = create_task(
        db,
        task_type="question_generation",
        params=serializable_params,
        total_steps=len(payload.entity_ids),
    )
    db.commit()

    # 后台启动出题任务
    from app.core.question_generator import execute_question_task
    background_tasks.add_task(execute_question_task, task.id, serializable_params)

    logger.info(
        "Question task %s created for doc %s (%d entities)",
        task.id, payload.document_id, len(payload.entity_ids),
    )
    return TaskCreateResponse(task_id=task.id, status="pending")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """查询任务状态（含进度）。"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        total_steps=task.total_steps,
        completed_steps=task.completed_steps,
        current_step=task.current_step_description,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error_message=task.error_message if task.status == "failed" else None,
    )


@router.get("/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """获取任务完成结果。仅 completed 状态可获取。"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"Task is {task.status}, not completed")
    return TaskResultResponse(
        task_id=task.id,
        status=task.status,
        result=task.result,
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    task_type: str | None = None,
    status: str | None = None,
    document_id: uuid.UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取任务列表。"""
    if document_id:
        # 按文档过滤：params JSONB 中包含 document_id
        tasks = (
            db.query(Task)
            .filter(
                Task.task_type == (task_type or "question_generation"),
                Task.params["document_id"].astext == str(document_id),
            )
            .order_by(Task.created_at.desc())
            .limit(limit)
            .all()
        )
    else:
        tasks = get_tasks(db, task_type=task_type, status=status, limit=limit)
    return TaskListResponse(
        tasks=[
            TaskItem(
                task_id=t.id,
                task_type=t.task_type,
                status=t.status,
                total_steps=t.total_steps,
                completed_steps=t.completed_steps,
                current_step=t.current_step_description,
                params=t.params,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
                error_message=t.error_message if t.status == "failed" else None,
            )
            for t in tasks
        ],
    )
