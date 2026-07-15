"""
M2.8 实体提取器 — LLM 从文档子块中提取知识实体。
"""

import json
import re
import time
from uuid import UUID

from openai import OpenAI

from app.core.config import settings
from app.core.logging import logger

EXTRACT_PROMPT = """[SYSTEM] 你是一位知识工程专家。请从以下教材内容中提取所有重要实体。

【输出格式要求】
你必须输出纯 JSON 数组，不允许包含任何其他内容：
[
  {{"name": "实体名称", "type": "实体类型", "description": "简短描述（15字以内）"}},
  ...
]

【实体类型】
- concept: 核心概念（如"自我意识"、"形式运算"）
- theorist: 心理学家/理论家（如"皮亚杰"、"埃里克森"）
- theory: 理论名称（如"认知发展阶段理论"）
- method: 研究方法（如"实验法"、"访谈法"）
- fact: 关键事实或研究发现

【提取规则】
1. 只提取对理解该章节必要的实体，不提取无关细节
2. 同一实体多次出现只提取一次
3. 描述应简洁，突出该实体的核心含义

【教材内容】
{content}

【请开始提取实体】"""


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def extract_entities(content: str) -> list[dict]:
    """调用 LLM 从教材内容中提取实体列表。

    Returns:
        list[dict], 每项含 name / type / description。
    """
    client = _get_llm_client()
    prompt = EXTRACT_PROMPT.format(content=content)

    t0 = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=settings.graph_llm_timeout,
        )
        raw = response.choices[0].message.content or ""
        entities = _parse_entities(raw)
        logger.info("Entity extraction: %d entities in %.3fs", len(entities), time.monotonic() - t0)
        return entities
    except Exception as e:
        logger.error("Entity extraction LLM call failed: %s", e)
        return []


def _parse_entities(raw: str) -> list[dict]:
    """从 LLM 响应中解析 JSON 实体列表，容错处理 markdown 代码块包裹和散装文本。"""
    text = raw.strip()

    # 移除 ```json ... ``` 或 ``` ... ``` 包裹
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()

    # 尝试正则抽取 JSON 数组
    json_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        entities = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Entity extraction: failed to parse LLM response as JSON")
        return []

    if not isinstance(entities, list):
        return []

    validated = []
    seen_names = set()
    for item in entities:
        name = str(item.get("name", "")).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        validated.append({
            "name": name,
            "type": str(item.get("type", "concept")),
            "description": str(item.get("description", ""))[:100],
        })
    return validated
