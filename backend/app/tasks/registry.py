"""
M3.2 任务注册表 — @register_task 装饰器 + 工厂函数。
M3.3: 新增 RegistryBasedTaskFactory（注入依赖的任务工厂）。
"""

from uuid import UUID

from app.tasks.base import BaseTask

_task_registry: dict[str, type[BaseTask]] = {}


def register_task(cls: type[BaseTask]) -> type[BaseTask]:
    """类装饰器：将任务类注册到全局注册表。"""
    _task_registry[cls.task_type] = cls
    return cls


def get_task_class(task_type: str) -> type[BaseTask]:
    """按 task_type 查找任务类。"""
    if task_type not in _task_registry:
        raise ValueError(f"Unknown task type: {task_type}")
    return _task_registry[task_type]


def instantiate_task(task_type: str, task_id: UUID, params: dict) -> BaseTask:
    """工厂方法：创建任务实例（无 DI）。"""
    cls = get_task_class(task_type)
    return cls(task_id, params)


def get_all_task_types() -> list[dict]:
    """返回所有已注册任务类型的元信息。"""
    return [
        {
            "task_type": cls.task_type,
            "display_name": cls.display_name,
            "icon": cls.icon,
            "description": cls.description,
        }
        for cls in _task_registry.values()
    ]


# ── M3.3 RegistryBasedTaskFactory（依赖注入工厂） ─────────────


class RegistryBasedTaskFactory:
    """基于注册表的任务工厂，注入外部依赖到任务实例。

    实现 TaskFactory 接口（app.core.interfaces.TaskFactory）。
    通过构造函数接收所有可能需要的服务，按 task_type 分派。
    """

    def __init__(
        self,
        question_generator=None,
        entity_extractor=None,
        relation_extractor=None,
        llm_client=None,
    ):
        self._question_generator = question_generator
        self._entity_extractor = entity_extractor
        self._relation_extractor = relation_extractor
        self._llm_client = llm_client

    def create(
        self,
        task_type: str,
        task_id: UUID,
        document_id: UUID,
        params: dict,
    ):
        """创建任务实例，注入对应依赖。"""
        # 确保 document_id 在 params 中
        p = dict(params)
        p["document_id"] = str(document_id)

        if task_type == "question_generation":
            from app.tasks.question_task import QuestionTask

            return QuestionTask(
                task_id=task_id,
                params=p,
                question_generator=self._question_generator,
                llm_client=self._llm_client,
            )

        if task_type == "entity_extraction":
            from app.tasks.graph_task import EntityExtractionTask

            return EntityExtractionTask(
                task_id=task_id,
                params=p,
                entity_extractor=self._entity_extractor,
                relation_extractor=self._relation_extractor,
            )

        if task_type == "graph_generation":
            from app.tasks.graph_task import GraphTask

            return GraphTask(
                task_id=task_id,
                params=p,
                entity_extractor=self._entity_extractor,
                relation_extractor=self._relation_extractor,
            )

        raise ValueError(f"Unknown task type for factory: {task_type}")
