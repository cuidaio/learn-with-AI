"""
M2.8.2 出题生成器 — 并行出题 + 异步任务 + 题型扩展（单/多选）。
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.graph_store import get_fact_chain
from app.core.logging import logger
from app.core.task_manager import complete_task, fail_task, update_task_progress, update_task_status
from app.database import SessionLocal
from app.models import Entity, Question

QUESTION_PROMPT = """[SYSTEM] 你是一位考研命题专家。以下是一组以【实体-关系-实体】三元组形式呈现的**事实链**，来源于教材。

【事实链】
{fact_chain}

注意：以下三元组中的关系类型（如 contains、causes、contrasts 等）仅用于描述实体间的连接关系，**不是考查对象**。

【目标知识点】
{target_entity_name}: {target_entity_description}

【题目要求】
请基于上述事实链，生成以下题型的题目：
{type_instructions}

【输出格式】
纯 JSON 数组：
{format_example}

【题型说明】
- choice: 单选题，4个选项（A/B/C/D），answer 为单个大写字母
- multi_choice: 多选题，5个选项（A/B/C/D/E），answer 为数组 ["A", "C"]
- fill: 填空题，题干中用 "____" 表示填空位置
- short_answer: 简答题，以"简述"或"为什么"开头
- essay: 论述题，以"论述"或"分析"开头

【Bloom 层级】
- remember: 识记（定义、名称、事实）
- understand: 理解（解释、举例、总结）
- apply: 应用（运用概念解决新问题）
- analyze: 分析（区分、组织、归因）
- evaluate: 评价（判断、批判、辩护）

【请开始生成题目】"""


FORMAT_EXAMPLES = {
    "choice": """[
  {{"type": "choice", "stem": "以下哪项属于自我意识的核心成分？", "options": {{"A": "自我概念", "B": "认知失调", "C": "皮亚杰理论", "D": "形式运算"}}, "answer": "A", "explanation": "自我概念是自我意识的核心成分之一", "bloom_level": "remember", "difficulty_estimate": 0.3}},
  {{"type": "choice", "stem": "谁提出了形式运算阶段？", "options": {{"A": "埃里克森", "B": "维果茨基", "C": "皮亚杰", "D": "弗洛伊德"}}, "answer": "C", "explanation": "皮亚杰提出了认知发展理论，包括形式运算阶段", "bloom_level": "remember", "difficulty_estimate": 0.2}}
]""",
    "multi_choice": """[
  {{"type": "multi_choice", "stem": "以下哪些属于皮亚杰认知发展的阶段？", "options": {{"A": "感知运动阶段", "B": "前运算阶段", "C": "具体运算阶段", "D": "形式运算阶段", "E": "后形式运算阶段"}}, "answer": ["A", "B", "C", "D"], "explanation": "皮亚杰提出四个认知发展阶段", "bloom_level": "remember", "difficulty_estimate": 0.4}}
]""",
    "fill": """[
  {{"type": "fill", "stem": "自我意识的核心成分包括自我概念、自我评价和____。", "answer": "自我体验", "bloom_level": "remember", "difficulty_estimate": 0.3}}
]""",
    "short_answer": """[
  {{"type": "short_answer", "stem": "简述皮亚杰和维果茨基在认知发展理论上的主要区别。", "answer": "皮亚杰强调认知发展的阶段性，认为发展先于学习；维果茨基强调社会文化的影响，认为学习先于发展并提出最近发展区概念。", "bloom_level": "understand", "difficulty_estimate": 0.5}}
]""",
    "essay": """[
  {{"type": "essay", "stem": "论述自我意识在青少年个性发展中的作用。", "answer": "自我意识是个体对自身及其与外界关系的认识和体验。在青少年期，自我意识的发展推动了个性的形成和完善...（不少于200字）", "bloom_level": "evaluate", "difficulty_estimate": 0.8}}
]""",
}


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


VALID_BLOOM = {"remember", "understand", "apply", "analyze", "evaluate"}
VALID_TYPES = {"fill", "short_answer", "essay", "choice", "multi_choice"}


def format_fact_chain(fact_chain: dict) -> str:
    """将事实链格式化为字符串，关系类型作为连接词，不作为考查对象。"""
    entity = fact_chain.get("entity")
    if not entity:
        return ""

    lines = [f"目标知识点：{entity['name']}（{entity.get('type', '?')}）"]
    if entity.get("description"):
        lines.append(f"描述：{entity['description']}")
    lines.append("")

    if fact_chain["relations"]:
        lines.append("关联关系：")
        for r in fact_chain["relations"]:
            rel_type = r["relation_type"].replace("_", " ")
            lines.append(f"  {r['source_name']} [ {rel_type} ] {r['target_name']}")
            if r.get("description"):
                lines.append(f"    {r['description']}")
        lines.append("")

    if fact_chain["related_entities"]:
        lines.append("相关实体：")
        for e in fact_chain["related_entities"]:
            desc = e.get("description", "") or ""
            lines.append(f"  - {e['name']}（{e.get('type', '?')}）: {desc}")

    return "\n".join(lines)


def _build_counts_per_type(
    total_count: int,
    num_entities: int,
    active_types: set[str],
    type_weights: dict[str, float] | None = None,
) -> dict[str, int]:
    """计算每个实体应生成的各题型数量。"""
    if type_weights is None:
        type_weights = {
            "choice": 0.30,
            "multi_choice": 0.20,
            "fill": 0.20,
            "short_answer": 0.15,
            "essay": 0.15,
        }
    per_entity = max(1, round(total_count / max(1, num_entities)))
    counts = {}
    assigned = 0
    sorted_types = sorted(
        [(t, w) for t, w in type_weights.items() if t in active_types],
        key=lambda x: -x[1],
    )
    for t, w in sorted_types:
        c = max(0, round(per_entity * w))
        if assigned + c > per_entity:
            c = max(0, per_entity - assigned)
        counts[t] = c
        assigned += c
    # 补足差额
    if assigned < per_entity and active_types:
        first = list(active_types)[0]
        counts[first] = counts.get(first, 0) + (per_entity - assigned)
    return counts


def _build_type_instructions(counts: dict[str, int]) -> str:
    """构建题型数量说明。"""
    label_map = {
        "choice": "单选题",
        "multi_choice": "多选题",
        "fill": "填空题",
        "short_answer": "简答题",
        "essay": "论述题",
    }
    parts = []
    for t in ["choice", "multi_choice", "fill", "short_answer", "essay"]:
        c = counts.get(t, 0)
        if c > 0:
            parts.append(f"- {label_map[t]}（{t}）：{c}道")
    return "\n".join(parts)


def _build_format_example(active_types: set[str]) -> str:
    """构建题型对应的输出格式示例。"""
    parts = []
    for t in ["choice", "multi_choice", "fill", "short_answer", "essay"]:
        if t in active_types:
            parts.append(FORMAT_EXAMPLES[t])
    return "\n\n".join(parts)


def _validate_question(item: dict) -> dict | None:
    """校验单道题目，返回规范化 dict 或 None。"""
    qtype = str(item.get("type", "")).strip()
    if qtype not in VALID_TYPES:
        return None

    stem = str(item.get("stem", "")).strip()
    answer = item.get("answer")
    bloom = str(item.get("bloom_level", "")).strip()
    difficulty = item.get("difficulty_estimate", 0.5)

    if not stem or not answer:
        return None

    # 题型特定校验
    if qtype == "fill":
        a = str(answer).strip()
        if "____" not in stem or len(a) > 50:
            return None
    elif qtype == "short_answer":
        a = str(answer).strip()
        if not (stem.startswith("简述") or stem.startswith("为什么")) or len(a) < 20:
            return None
    elif qtype == "essay":
        a = str(answer).strip()
        if not (stem.startswith("论述") or stem.startswith("分析")) or len(a) < 100:
            return None
    elif qtype == "choice":
        options = item.get("options")
        if not options or not isinstance(options, dict) or len(options) < 2:
            return None
        a = str(answer).strip()
        if a not in options:
            return None
    elif qtype == "multi_choice":
        options = item.get("options")
        if not options or not isinstance(options, dict) or len(options) < 2:
            return None
        if not isinstance(answer, list) or len(answer) < 2:
            return None
        for a in answer:
            if a not in options:
                return None

    if bloom not in VALID_BLOOM:
        bloom = "remember"
    try:
        difficulty = float(difficulty)
    except (ValueError, TypeError):
        difficulty = 0.5
    difficulty = max(0.0, min(1.0, difficulty))

    result: dict = {
        "type": qtype,
        "stem": stem,
        "answer": json.dumps(answer, ensure_ascii=False) if isinstance(answer, list) else str(answer),
        "bloom_level": bloom,
        "difficulty_estimate": difficulty,
    }
    if qtype in ("choice", "multi_choice"):
        result["options"] = options
    return result


def _parse_questions(raw: str) -> list[dict | None]:
    """解析 LLM JSON 响应并逐条校验。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Question generation: failed to parse LLM response as JSON")
        return []

    if not isinstance(items, list):
        return []

    return [_validate_question(item) for item in items]


def _generate_for_entity(
    client: OpenAI,
    entity: Entity,
    fact_text: str,
    counts: dict[str, int],
) -> list[dict]:
    """为单个实体调用 LLM 生成题目。"""
    active_types = {t for t, c in counts.items() if c > 0}
    type_instructions = _build_type_instructions(counts)
    format_example = _build_format_example(active_types)

    prompt = QUESTION_PROMPT.format(
        fact_chain=fact_text,
        target_entity_name=entity.name,
        target_entity_description=entity.description or entity.entity_type or "",
        type_instructions=type_instructions,
        format_example=format_example,
    )

    t0 = time.monotonic()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
        timeout=settings.question_timeout,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )
    raw = response.choices[0].message.content or ""
    parsed = _parse_questions(raw)
    valid = [q for q in parsed if q is not None]
    logger.info(
        "Questions for '%s': %d raw → %d valid in %.3fs",
        entity.name, len(parsed), len(valid), time.monotonic() - t0,
    )
    return valid


def save_questions(
    db: Session,
    document_id: UUID,
    questions: list[dict],
    entity_ids: list[UUID] | None = None,
) -> int:
    """批量保存题目到数据库。"""
    saved = 0
    for q in questions:
        row = Question(
            document_id=document_id,
            question_type=q["type"],
            stem=q["stem"],
            answer=q["answer"],
            options=q.get("options"),
            bloom_level=q.get("bloom_level"),
            difficulty_estimate=q.get("difficulty_estimate"),
            source_entity_ids=entity_ids,
        )
        db.add(row)
        saved += 1
    db.flush()
    logger.info("Saved %d questions for document %s", saved, document_id)
    return saved


# ── 同步入口（旧版兼容，单次调用，用于直接测试） ─────────────

def generate_questions(
    db: Session,
    document_id: UUID,
    entity_ids: list[UUID] | None = None,
    types: list[str] | None = None,
    count_per_type: int = 3,
) -> list[dict]:
    """为文档生成题目（同步，兼容旧调用）。"""
    target_entities = []
    if entity_ids:
        target_entities = (
            db.query(Entity)
            .filter(Entity.id.in_(entity_ids), Entity.document_id == document_id)
            .all()
        )
    else:
        from app.core.graph_store import get_high_confidence_entities
        target_entities = get_high_confidence_entities(db, document_id)

    if not target_entities:
        logger.warning("Question generation: no valid entities found")
        return []

    if types:
        valid = {t for t in types if t in VALID_TYPES}
    else:
        valid = VALID_TYPES

    client = _get_llm_client()
    all_questions: list[dict] = []

    for entity in target_entities:
        fact_chain = get_fact_chain(db, document_id, entity.id, max_hops=2)
        fact_text = format_fact_chain(fact_chain)
        if not fact_text.strip():
            continue

        counts = {}
        for t in valid:
            counts[t] = count_per_type

        try:
            questions = _generate_for_entity(client, entity, fact_text, counts)
            all_questions.extend(questions)
        except Exception as e:
            logger.error("Question generation for '%s' failed: %s", entity.name, e)
            continue

    return all_questions


# ── 异步任务入口 ─────────────────────────────────────────

def execute_question_task(task_id: UUID, params: dict) -> None:
    """后台执行出题任务（parallel + progress tracking）。"""
    db = SessionLocal()
    try:
        document_id = UUID(params["document_id"]) if isinstance(params["document_id"], str) else params["document_id"]
        entity_ids = [UUID(e) if isinstance(e, str) else e for e in params.get("entity_ids", [])]
        total_count = params.get("total_count", 18)
        selected_types = set(params.get("types", ["choice", "multi_choice", "fill", "short_answer", "essay"]))
        type_weights = params.get("type_weights")

        entities = (
            db.query(Entity)
            .filter(Entity.id.in_(entity_ids), Entity.document_id == document_id)
            .all()
        )
        if not entities:
            fail_task(db, task_id, "No valid entities found")
            db.commit()
            return

        update_task_status(db, task_id, "running")
        update_task_progress(
            db, task_id, 0,
            f"准备处理 {len(entities)} 个知识点",
        )
        db.commit()

        # 为每个实体构建事实链
        tasks = []
        for entity in entities:
            fact_chain = get_fact_chain(db, document_id, entity.id, max_hops=2)
            fact_text = format_fact_chain(fact_chain)
            if fact_text.strip():
                tasks.append((entity, fact_text))

        if not tasks:
            fail_task(db, task_id, "No fact chains available")
            db.commit()
            return

        update_task_progress(
            db, task_id, 0,
            f"开始并行出题（{len(tasks)} 个知识点）",
        )
        db.commit()

        counts_per_entity = _build_counts_per_type(
            total_count, len(tasks), selected_types, type_weights,
        )

        client = _get_llm_client()
        all_questions: list[dict] = []
        failed_names: list[str] = []
        completed = 0

        with ThreadPoolExecutor(max_workers=settings.question_workers) as executor:
            future_map = {
                executor.submit(_generate_for_entity, client, entity, fact_text, counts_per_entity): entity
                for entity, fact_text in tasks
            }

            for future in as_completed(future_map):
                entity = future_map[future]
                try:
                    questions = future.result(timeout=settings.question_timeout)
                    all_questions.extend(questions)
                except Exception as e:
                    logger.error("Entity '%s' failed: %s", entity.name, e)
                    failed_names.append(entity.name)
                completed += 1
                update_task_progress(
                    db, task_id, completed,
                    f"已完成 {completed}/{len(tasks)} 个知识点",
                )
                db.commit()

        # 保存题目到数据库
        entity_id_list = [e.id for e in entities]
        saved = save_questions(db, document_id, all_questions, entity_id_list)

        # 类型统计
        types_breakdown: dict[str, int] = {}
        for q in all_questions:
            t = q["type"]
            types_breakdown[t] = types_breakdown.get(t, 0) + 1

        complete_task(db, task_id, {
            "questions": all_questions,
            "metadata": {
                "total_entities": len(tasks),
                "successful_entities": len(tasks) - len(failed_names),
                "failed_entities": failed_names,
                "total_generated": len(all_questions),
                "saved_to_db": saved,
                "types_breakdown": types_breakdown,
            },
        })
        db.commit()
        logger.info(
            "Task %s done: %d questions for %d entities (failed: %s)",
            task_id, len(all_questions), len(tasks), failed_names or "none",
        )

    except Exception as e:
        logger.error("Task %s crashed: %s", task_id, e, exc_info=True)
        try:
            fail_task(db, task_id, str(e))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
