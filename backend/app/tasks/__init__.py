"""
M3.2 任务抽象系统 — 统一任务注册表 + 基类。
M3.3: 导出 RegistryBasedTaskFactory。
"""

from app.tasks.base import BaseTask, TaskStatus
from app.tasks.registry import (
    RegistryBasedTaskFactory,
    get_all_task_types,
    get_task_class,
    instantiate_task,
    register_task,
)

# 确保所有任务类被导入，触发 @register_task 装饰器
from app.tasks import graph_task, question_task  # noqa: F401

__all__ = [
    "BaseTask",
    "TaskStatus",
    "register_task",
    "get_task_class",
    "instantiate_task",
    "get_all_task_types",
    "RegistryBasedTaskFactory",
]
