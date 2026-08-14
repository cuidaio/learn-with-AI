"""
M3.2 任务抽象基类 — 定义任务生命周期、输入输出契约。
M3.3: 移除 execute 的 db 参数，添加 document_id 属性。
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class TaskStatus:
    """任务状态常量。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseTask(ABC):
    """任务抽象基类。

    子类必须定义 task_type / display_name / icon 作为类属性，
    并实现 execute() / get_card_fields() 方法。

    M3.3: 外部依赖通过构造函数注入，不直接 import。
          子类在 __init__ 中接收注入的服务并保存到 self._*。
    """

    task_type: str = "base"
    display_name: str = "任务"
    icon: str = "📋"
    description: str = ""
    timeout_seconds: int = 300

    def __init__(self, task_id: UUID, params: dict):
        self.task_id = task_id
        self.params = params
        # 从 params 中提取 document_id
        raw = params.get("document_id")
        self.document_id: UUID | None = UUID(raw) if raw and isinstance(raw, str) else raw

    @abstractmethod
    def execute(self) -> None:
        """执行任务核心逻辑。

        M3.3: 不再接收 db 参数。子类通过注入的服务自行管理持久化和状态更新。
        """
        ...

    def get_card_fields(self) -> dict:
        """创建任务卡片时填充的默认字段。"""
        return {
            "card_title": self.display_name,
            "card_icon": self.icon,
            "result_content_type": None,
            "total_steps": None,
        }
