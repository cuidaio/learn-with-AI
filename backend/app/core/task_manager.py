"""
M2.8.2 + M3.2 任务生命周期管理 — create → update progress → complete / fail.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Task


def _task_to_card(task: Task) -> dict:
    """Task ORM → 前端卡片 dict（TaskCardItem 所需字段）。"""
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "card_title": task.card_title,
        "card_icon": task.card_icon,
        "result_content_type": task.result_content_type,
        "is_default": bool(task.is_default),
        "progress": task.progress or 0,
        "progress_text": task.progress_text,
        "params": task.params,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "error_message": task.error_message if task.status == "failed" else None,
    }


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


def create_task_with_card(
    db: Session,
    task_type: str,
    params: dict,
    card_title: str,
    card_icon: str,
    result_content_type: str,
    total_steps: int | None = None,
) -> Task:
    """创建任务并设置卡片字段（M3 卡片视图）。"""
    task = create_task(db, task_type=task_type, params=params, total_steps=total_steps)
    task.card_title = card_title
    task.card_icon = card_icon
    task.result_content_type = result_content_type
    db.flush()
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
    # M3: sync progress/progress_text
    if task.total_steps and task.total_steps > 0:
        task.progress = int((task.completed_steps / task.total_steps) * 100)
    if description is not None:
        task.progress_text = description
    db.flush()


def complete_task(db: Session, task_id: uuid.UUID, result: dict) -> None:
    """标记任务为 completed，保存结果。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return
    task.status = "completed"
    task.result = result
    task.completed_at = datetime.utcnow()
    task.progress = 100
    task.progress_text = "已完成"
    # M3: if result contains content_type, set it on the task
    content_type = result.get("content_type") if isinstance(result, dict) else None
    if content_type:
        task.result_content_type = content_type
    db.flush()
    # data 可能是 list（实体列表）或 dict（图谱/题目），统一处理
    try:
        data_val = result.get("data", {}) if isinstance(result, dict) else {}
        if isinstance(data_val, dict):
            qty = len(data_val.get("questions", result.get("questions", [])))
        elif isinstance(data_val, (list, tuple)):
            qty = len(data_val)
        else:
            qty = 0
    except Exception:
        qty = 0
    logger.info("Task %s completed: %d items", task_id, qty)


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


# ── M3.3 TaskManager (with DI support) ────────────────────────────────


class TaskManager:
    """统一任务管理器：创建 / 调度 / 查询 / 重试 / 删除。

    M3.3: 支持通过 task_factory 注入依赖到任务实例。
          如果不提供 task_factory，降级为 M3.2 的 dispatch 模式。

    使用方式（在 route 中）：
        task_manager = TaskManager(task_factory=factory)
        task_manager.create_and_schedule(db, ...)
    """

    def __init__(self, task_factory=None, task_store=None):
        self._task_factory = task_factory
        self._task_store = task_store

    # ── 创建与调度 ──

    def create_and_schedule(
        self,
        db: Session,
        task_type: str,
        params: dict,
        background_tasks,
        card_title: str | None = None,
        card_icon: str | None = None,
        result_content_type: str | None = None,
        total_steps: int | None = None,
        use_registry: bool = True,
    ) -> Task:
        """创建任务记录 + 获取卡片字段（从 registry）。

        如果 use_registry=True，从 BaseTask 子类的 get_card_fields()
        获取默认卡片字段，参数中的 card_* 会覆盖默认值。
        """
        card_fields = {}
        if use_registry:
            try:
                from app.tasks.registry import get_task_class

                cls = get_task_class(task_type)
                card_fields = cls(None, {}).get_card_fields()  # type: ignore[arg-type]
            except (ValueError, ImportError):
                pass

        task = create_task_with_card(
            db,
            task_type=task_type,
            params=params,
            card_title=card_title or card_fields.get("card_title"),
            card_icon=card_icon or card_fields.get("card_icon"),
            result_content_type=result_content_type or card_fields.get("result_content_type"),
            total_steps=total_steps or card_fields.get("total_steps"),
        )

        self._schedule_execution(db, task, background_tasks)
        return task

    def _schedule_execution(self, db: Session, task: Task, background_tasks) -> None:
        """调度后台执行：优先使用 task_factory（注入 DI），否则降级为旧 dispatch。"""
        if self._task_factory is not None:
            self._schedule_with_factory(task, background_tasks)
        else:
            self._schedule_legacy(task, background_tasks)

    def _schedule_with_factory(self, task: Task, background_tasks) -> None:
        """使用 task_factory 创建 BaseTask 实例并调度 execute()。"""
        try:
            doc_id = uuid.UUID(task.params["document_id"])
        except (KeyError, ValueError):
            logger.warning("Task %s: no document_id in params, using legacy dispatch", task.id)
            self._schedule_legacy(task, background_tasks)
            return

        try:
            instance = self._task_factory.create(
                task_type=task.task_type,
                task_id=task.id,
                document_id=doc_id,
                params=task.params,
            )
        except ValueError as e:
            logger.warning("Task %s: factory error (%s), using legacy dispatch", task.id, e)
            self._schedule_legacy(task, background_tasks)
            return

        background_tasks.add_task(instance.execute)

    def _schedule_legacy(self, task: Task, background_tasks) -> None:
        """旧版 dispatch：直接调用现有执行函数。"""
        if task.task_type == "question_generation":
            from app.core.question_generator import execute_question_task

            background_tasks.add_task(execute_question_task, task.id, task.params)
        elif task.task_type == "entity_extraction":
            from app.core.graph_builder import execute_entity_extraction_task

            doc_id = uuid.UUID(task.params["document_id"])
            title = task.params.get("title", task.card_title or "实体提取")
            background_tasks.add_task(execute_entity_extraction_task, task.id, doc_id, title)
        elif task.task_type == "graph_generation":
            self._schedule_graph_generation(task, background_tasks)
        else:
            logger.warning("No executor for task type: %s", task.task_type)

    def _schedule_graph_generation(self, task: Task, background_tasks) -> None:
        """调度知识图谱构建任务（旧版 _execute 闭包）。"""
        from app.core.graph_builder import extract_and_save_entities, extract_and_save_relations

        def _execute(tid: uuid.UUID, pid: dict) -> None:
            from app.database import SessionLocal

            db2 = SessionLocal()
            try:
                from app.core.graph_store import get_full_graph

                doc_id = uuid.UUID(pid["document_id"])
                update_task_status(db2, tid, "running")
                db2.commit()

                from app.models import Entity

                existing_count = db2.query(Entity).filter(Entity.document_id == doc_id).count()
                if existing_count > 0:
                    update_task_progress(db2, tid, 0, "实体已存在，直接进行关系提取")
                    db2.commit()
                else:
                    update_task_progress(db2, tid, 0, "开始实体提取")
                    db2.commit()
                    has_entities = extract_and_save_entities(db2, doc_id)
                    if not has_entities:
                        fail_task(db2, tid, "实体提取失败：未提取到任何实体")
                        db2.commit()
                        return
                    update_task_progress(db2, tid, 1, "实体提取完成，开始关系提取")
                    db2.commit()

                extract_and_save_relations(db2, doc_id)

                doc_title = db2.query(Task.card_title).filter(Task.id == tid).scalar() or "知识图谱"
                graph = get_full_graph(db2, doc_id)
                complete_task(db2, tid, {
                    "content_type": "knowledge_graph",
                    "title": doc_title,
                    "data": graph,
                })
                db2.commit()
            except Exception as e:
                logger.error("Graph task %s failed: %s", tid, e, exc_info=True)
                try:
                    fail_task(db2, tid, str(e))
                    db2.commit()
                except Exception:
                    pass
            finally:
                db2.close()

        background_tasks.add_task(_execute, task.id, task.params)

    # ── 查询 ──

    def get_card_list(self, db: Session, document_id: uuid.UUID | None = None) -> list[dict]:
        """获取任务卡片列表。"""
        q = db.query(Task)
        if document_id:
            q = q.filter(Task.params["document_id"].astext == str(document_id))
        tasks = q.order_by(Task.created_at.desc()).limit(100).all()
        return [_task_to_card(t) for t in tasks]

    def get_status_dict(self, db: Session, task_id: uuid.UUID) -> dict | None:
        """获取任务状态 dict（供 TaskCard 轮询）。"""
        task = get_task(db, task_id)
        if not task:
            return None
        d = _task_to_card(task)
        d["result"] = task.result
        return d


task_manager = TaskManager()


def configure_task_manager(task_factory=None, task_store=None) -> TaskManager:
    """配置全局 task_manager 的依赖（从 DI 容器注入）。

    在 app lifespan 中调用，不影响已有 API 接口。
    """
    global task_manager
    if task_factory is not None:
        task_manager._task_factory = task_factory
    if task_store is not None:
        task_manager._task_store = task_store
    return task_manager
