"""
M2.8 关系提取器 — LLM 从实体列表 + 文档内容中提取关系三元组。
"""

import json
import re
import time

from openai import OpenAI

from app.core.config import settings
from app.core.logging import logger

RELATION_PROMPT = """[SYSTEM] 你是一位知识工程专家。以下是已从教材中提取的实体列表。请识别这些实体之间的关系。

【输出格式要求】
你必须输出纯 JSON 数组，不允许包含任何其他内容：
[
  {{"source": "源实体名称", "target": "目标实体名称", "relation_type": "关系类型", "description": "关系描述（15字以内）"}},
  ...
]

【关系类型】
- is_a: 上下位关系（如"自我意识" is_a "心理现象"）
- contains: 包含关系（如"自我意识" contains "自我概念"）
- causes: 因果关系（如"认知发展" causes "自我意识变化"）
- contrasts: 对比关系（如"皮亚杰" contrasts "维果茨基"）
- precedes: 时序关系（如"形式运算" precedes "后形式运算"）
- applies_to: 应用于（如"皮亚杰理论" applies_to "教育实践"）
- develops: 发展过程（如"自我评价" develops "自我概念"）

【提取规则】
1. 只提取文本中明确支持的关系，不凭空推测
2. source 和 target 必须来自提供的实体列表
3. relation_type 必须使用上述枚举值之一

【实体列表】
{entities}

【教材内容参考】
{content}

【请开始提取关系】

注意：直接输出JSON数组即可，不要包含任何推理过程、分析说明或markdown标记。"""


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def extract_relations(content: str, entity_names: list[str]) -> list[dict]:
    """调用 LLM 从实体列表中提取关系。

    Args:
        content: 文档原始内容（过长时会自动截断）。
        entity_names: 已提取的实体名称列表。

    Returns:
        list[dict], 每项含 source / target / relation_type / description。
    """
    client = _get_llm_client()

    entities_str = ", ".join(entity_names)
    prompt = RELATION_PROMPT.format(content=content, entities=entities_str)

    t0 = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
            timeout=settings.graph_llm_timeout,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = response.choices[0].message.content or ""
        relations = _parse_relations(raw, set(entity_names))
        logger.info("Relation extraction: %d/%d relations in %.3fs (raw len=%d)", len(relations), len(entity_names), time.monotonic() - t0, len(raw))
        if not relations and raw.strip():
            logger.debug("Relation raw response (first 200): %s", raw[:200])
        return relations
    except Exception as e:
        logger.error("Relation extraction LLM call failed: %s", e)
        return []


def _parse_relations(raw: str, valid_names: set[str]) -> list[dict]:
    """解析 LLM JSON 响应，支持 markdown 代码块、散装文本和截断 JSON。"""
    text = raw.strip()

    # 移除 ```json ... ``` 或 ``` ... ``` 包裹
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()

    # 尝试完整 JSON 解析（json_object 模式下可能返回 {"relations": [...]}）
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return _filter_relations(parsed, valid_names)
        if isinstance(parsed, dict):
            for key in ("relations", "relationships", "data", "items", "result"):
                val = parsed.get(key)
                if isinstance(val, list):
                    return _filter_relations(val, valid_names)
    except json.JSONDecodeError:
        pass

    # 定位 JSON 数组区域（兼容截断 JSON）
    start_bracket = text.find("[")
    end_bracket = text.rfind("]")
    if start_bracket != -1 and end_bracket > start_bracket:
        candidate = text[start_bracket : end_bracket + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return _filter_relations(parsed, valid_names)
        except json.JSONDecodeError:
            pass
        # 截断 JSON：逐个提取 { } 对象
        objs = re.findall(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', candidate, re.DOTALL)
        items = []
        for obj_str in objs:
            try:
                items.append(json.loads(obj_str))
            except json.JSONDecodeError:
                continue
        if items:
            return _filter_relations(items, valid_names)

    logger.warning("Relation extraction: failed to parse LLM response as JSON (raw=%d chars)", len(text))
    return []


def _filter_relations(items: list[dict], valid_names: set[str]) -> list[dict]:
    """过滤和校验关系列表。"""
    valid_types = {"is_a", "contains", "causes", "contrasts", "precedes", "applies_to", "develops"}
    validated = []
    seen = set()
    for item in items:
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        rtype = str(item.get("relation_type", "")).strip()
        if not source or not target or source not in valid_names or target not in valid_names:
            continue
        if rtype not in valid_types:
            continue
        dedup_key = f"{source}|{rtype}|{target}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        validated.append({
            "source": source,
            "target": target,
            "relation_type": rtype,
            "description": str(item.get("description", ""))[:100],
        })
    return validated
