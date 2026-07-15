"""
M2.8.2 任务生命周期管理 — create → update progress → complete / fail.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Task


def create_task(
    db: Session,
    task_type: str,
    params: dict,
    total_steps: int | None = None,
) -> Task:
    """创建任务，初始状态为 pending。"""
    task = Task(
        id=uuid.uuid4(),
        task_type=task_type,
        status="pending",
        params=params,
        total_steps=total_steps,
        completed_steps=0,
    )
    db.add(task)
    db.flush()
    logger.info("Task %s created (type=%s, steps=%s)", task.id, task_type, total_steps)
    return task


def update_task_status(db: Session, task_id: uuid.UUID, status: str) -> None:
    """更新任务状态及对应时间戳。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.warning("Task %s not found for status update", task_id)
        return
    task.status = status
    if status == "running" and not task.started_at:
        task.started_at = datetime.utcnow()
    elif status in ("completed", "failed"):
        task.completed_at = datetime.utcnow()
    db.flush()


def update_task_progress(
    db: Session,
    task_id: uuid.UUID,
    completed_steps: int | None = None,
    description: str | None = None,
) -> None:
    """更新任务进度。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    if completed_steps is not None:
        task.completed_steps = completed_steps
    if description is not None:
        task.current_step_description = description
    db.flush()


def complete_task(db: Session, task_id: uuid.UUID, result: dict) -> None:
    """标记任务为 completed，保存结果。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    task.status = "completed"
    task.result = result
    task.completed_at = datetime.utcnow()
    db.flush()
    logger.info("Task %s completed: %d questions", task_id, len(result.get("questions", [])))


def fail_task(db: Session, task_id: uuid.UUID, error_message: str) -> None:
    """标记任务为 failed，记录错误信息。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    task.status = "failed"
    task.error_message = error_message
    task.completed_at = datetime.utcnow()
    db.flush()
    logger.error("Task %s failed: %s", task_id, error_message)


def get_task(db: Session, task_id: uuid.UUID) -> Task | None:
    """获取单个任务。"""
    return db.query(Task).filter(Task.id == task_id).first()


def get_tasks(
    db: Session,
    task_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Task]:
    """获取任务列表，按创建时间倒序。"""
    q = db.query(Task)
    if task_type:
        q = q.filter(Task.task_type == task_type)
    if status:
        q = q.filter(Task.status == status)
    return q.order_by(Task.created_at.desc()).limit(limit).all()
