"""
PostgresTaskStore — TaskStore 接口的 PostgreSQL 实现。

包装现有 task_manager.py 的 DB 操作函数。
每个方法自行管理 Session（开/关），与 FastAPI route 的 Depends(get_db) 解耦。
"""

from typing import Any, Optional
from uuid import UUID

from app.core.interfaces import TaskStore
from app.database import SessionLocal
from app.models import Task


class PostgresTaskStore(TaskStore):
    """TaskStore 的 PostgreSQL 实现，包装 task_manager.py 既有函数。"""

    def get(self, task_id: UUID) -> Optional[Task]:
        from app.core.task_manager import get_task as _get

        db = SessionLocal()
        try:
            return _get(db, task_id)
        finally:
            db.close()

    def list(self, document_id: Optional[UUID] = None) -> list[Task]:
        from app.core.task_manager import get_tasks as _list

        db = SessionLocal()
        try:
            return _list(db, document_id=document_id)
        finally:
            db.close()

    def save(
        self,
        task_type: str,
        params: dict,
        card_title: str | None = None,
        card_icon: str | None = None,
        result_content_type: str | None = None,
        total_steps: int | None = None,
    ) -> Task:
        from app.core.task_manager import create_task_with_card as _create

        db = SessionLocal()
        try:
            task = _create(
                db,
                task_type=task_type,
                params=params,
                card_title=card_title,
                card_icon=card_icon,
                result_content_type=result_content_type,
                total_steps=total_steps,
            )
            db.commit()
            return task
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_status(self, task_id: UUID, status: str) -> None:
        from app.core.task_manager import update_task_status as _update

        db = SessionLocal()
        try:
            _update(db, task_id, status)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_progress(
        self,
        task_id: UUID,
        completed_steps: int | None = None,
        description: str | None = None,
    ) -> None:
        from app.core.task_manager import update_task_progress as _update

        db = SessionLocal()
        try:
            _update(db, task_id, completed_steps, description)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def complete(self, task_id: UUID, result: dict) -> None:
        from app.core.task_manager import complete_task as _complete

        db = SessionLocal()
        try:
            _complete(db, task_id, result)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def fail(self, task_id: UUID, error_message: str) -> None:
        from app.core.task_manager import fail_task as _fail

        db = SessionLocal()
        try:
            _fail(db, task_id, error_message)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete(self, task_id: UUID) -> bool:
        from app.core.task_manager import get_task as _get

        db = SessionLocal()
        try:
            task = _get(db, task_id)
            if not task:
                return False
            db.delete(task)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
