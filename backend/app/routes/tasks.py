"""
M2.8.2 + M3.2: 统一任务 API — 创建/状态/列表/类型/重试/删除。
"""

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.task_manager import (
    create_task,
    get_task,
    get_tasks,
    task_manager,
)
from app.database import get_db
from app.models import Document, Entity, Task
from app.schemas import (
    GraphTaskResponse,
    TaskCardItem,
    TaskCardListResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskItem,
    TaskListResponse,
    TaskResultResponse,
    TaskStatusResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── 统一创建（M3.2） ──────────────────────────────────────────────────────


class UnifiedTaskCreateRequest(BaseModel):
    task_type: str
    document_id: uuid.UUID
    params: dict = {}


@router.post("", response_model=TaskCreateResponse, status_code=201)
def create_task_unified(
    payload: UnifiedTaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """统一任务创建入口 (M3.2)。task_type + document_id + params。"""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    task_params = {"document_id": str(payload.document_id), **payload.params}
    task = task_manager.create_and_schedule(
        db,
        task_type=payload.task_type,
        params=task_params,
        background_tasks=background_tasks,
    )
    db.commit()
    logger.info("Unified task %s created (type=%s)", task.id, payload.task_type)
    return TaskCreateResponse(task_id=task.id, status="pending")


# ── 任务类型列表（M3.2） ──────────────────────────────────────────────────


class TaskTypeItem(BaseModel):
    task_type: str
    display_name: str
    icon: str
    description: str


class TaskTypeListResponse(BaseModel):
    types: list[TaskTypeItem]


@router.get("/types", response_model=TaskTypeListResponse)
def list_task_types():
    """获取所有已注册的任务类型。"""
    from app.tasks.registry import get_all_task_types

    return TaskTypeListResponse(types=[TaskTypeItem(**t) for t in get_all_task_types()])


# ── 出题任务（向后兼容） ──


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

    existing = (
        db.query(Entity.id)
        .filter(Entity.id.in_(payload.entity_ids), Entity.document_id == payload.document_id)
        .count()
    )
    if existing != len(payload.entity_ids):
        raise HTTPException(status_code=400, detail="Some entity_ids not found in document")

    raw_params = payload.model_dump()
    serializable_params = json.loads(json.dumps(raw_params, default=str))
    task = task_manager.create_and_schedule(
        db,
        task_type="question_generation",
        params={"document_id": str(payload.document_id), **serializable_params},
        background_tasks=background_tasks,
        card_title=f"{doc.title} 训练题",
    )
    db.commit()
    logger.info("Question task %s created for doc %s", task.id, payload.document_id)
    return TaskCreateResponse(task_id=task.id, status="pending")


# ── 知识图谱任务（向后兼容） ──


@router.post("/graph", response_model=GraphTaskResponse, status_code=201)
def create_graph_task(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """创建知识图谱构建任务。"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    task = task_manager.create_and_schedule(
        db,
        task_type="graph_generation",
        params={"document_id": str(document_id)},
        background_tasks=background_tasks,
        card_title=f"{doc.title} 知识图谱",
        use_registry=False,  # 手动设置卡片字段
    )
    # 覆盖 registry 默认值（graph_generation 未注册或默认不同）
    task.card_title = f"{doc.title} 知识图谱"
    task.card_icon = "📊"
    task.result_content_type = "knowledge_graph"
    db.commit()

    return GraphTaskResponse(task_id=task.id, status="pending")


# ── 卡片列表（M3） ──


@router.get("/cards", response_model=TaskCardListResponse)
def list_task_cards(
    document_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    """获取任务卡片列表（含 M3 卡片字段），按创建时间倒序。"""
    cards = task_manager.get_card_list(db, document_id)
    return TaskCardListResponse(
        tasks=[TaskCardItem(**c) for c in cards],
    )


# ── 旧版列表（兼容） ──


@router.get("", response_model=TaskListResponse)
def list_tasks(
    task_type: str | None = None,
    status: str | None = None,
    document_id: uuid.UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取任务列表（旧版兼容）。"""
    if document_id:
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


# ── 状态 / 结果 / 卡片 / 重试 / 删除 ──


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(task_id: uuid.UUID, db: Session = Depends(get_db)):
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


@router.get("/{task_id}/card")
def get_task_card(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """获取任务卡片详情（含卡片字段 + 结果），供 TaskCard 轮询。"""
    d = task_manager.get_status_dict(db, task_id)
    if not d:
        raise HTTPException(status_code=404, detail="Task not found")
    return d


@router.get("/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(task_id: uuid.UUID, db: Session = Depends(get_db)):
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


@router.post("/{task_id}/retry", response_model=TaskCreateResponse)
def retry_task(task_id: uuid.UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """重试失败的任务。"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    # 创建新任务（复用旧参数）
    new_task = create_task(
        db,
        task_type=task.task_type,
        params=task.params,
        total_steps=task.total_steps,
    )
    new_task.card_title = task.card_title
    new_task.card_icon = task.card_icon
    new_task.result_content_type = task.result_content_type

    # 自动删除旧失败任务卡片
    db.delete(task)
    db.commit()

    # 使用 TaskManager 调度执行
    task_manager._schedule_execution(db, new_task, background_tasks)

    return TaskCreateResponse(task_id=new_task.id, status="pending")


@router.delete("/{task_id}/delete", status_code=204)
def delete_task_card(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """删除任务卡片（软删除：仅移除卡片信息，保留底层数据）。"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_default:
        raise HTTPException(status_code=400, detail="Default card cannot be deleted")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/cancel", status_code=200)
def cancel_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """取消运行中的任务。"""
    from app.core.task_manager import fail_task

    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        fail_task(db, task_id, "用户取消")
        db.commit()
    return {"status": "cancelled"}
