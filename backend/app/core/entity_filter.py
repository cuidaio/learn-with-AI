"""
M3.6 实体后处理筛选 — 确定性丢弃 + 低置信度标记。

流程：
  LLM 输出实体列表 → post_process()
    ├── 纯数字/百分比 → discard
    ├── 文献引用 → discard
    ├── 无 introduction_context → review
    └── 有 introduction_context → keep
    ↓
  保留 keep + review 实体，discard 被移除
"""

import re
from typing import Any


def post_process(entities: list[dict]) -> list[dict]:
    """对去重后的实体列表执行后处理筛选。

    每个实体 dict 会被注入 filter_action / filter_reason 字段。
    返回过滤后的列表（discard 实体已被移除）。
    """
    result: list[dict] = []
    for entity in entities:
        name = entity.get("name", "")

        # 规则1：纯数字或百分比 → discard
        if re.match(r"^\d+\.?\d*%?$", name):
            entity["filter_action"] = "discard"
            entity["filter_reason"] = "numeric_value"
            continue

        # 规则2：文献引用格式 → discard
        if re.search(r"\([\w]+\s*,\s*\d{4}\)", name) or re.search(r"\(\d{4}\)", name):
            entity["filter_action"] = "discard"
            entity["filter_reason"] = "citation"
            continue

        # 规则3：检查 introduction_context 是否存在
        ctx = entity.get("introduction_context", "")
        if not ctx or not ctx.strip():
            entity["filter_action"] = "review"
            entity["filter_reason"] = "no_context"
        else:
            entity["filter_action"] = "keep"
            entity["filter_reason"] = "passed"

        result.append(entity)

    return result


def filter_entities_for_question(entities: list[Any]) -> list[Any]:
    """从实体列表中筛选出可出题的实体（filter_action = 'keep'）。"""
    return [e for e in entities if getattr(e, "filter_action", None) == "keep"]
