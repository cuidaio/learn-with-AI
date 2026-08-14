"""
M3.4 并行实体提取器 — 分块(sub_chunks) → 并行 LLM → 去重合并。

向后兼容：保留 extract_entities() 供旧路径和关系提取器使用。
"""

import asyncio
import json
import re
import time
from typing import Optional
from uuid import UUID

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import logger

EXTRACT_PROMPT = """[SYSTEM] 你是一位考研心理学辅导老师，擅长从教材中提取可出题的知识点。

【任务】从以下教材内容中提取所有【被介绍过】的知识实体。

"被介绍"的定义：该内容在文本中至少满足以下任一条件：
1. 被明确定义（如"X是指……""X是……"）
2. 被解释其特征或功能（如"X具有……特点""X表现为……"）
3. 被分类或列举（如"X包括……""X可分为……"）
4. 被赋予理论地位（如"X认为……""X提出……"）
5. 作为章节标题或小节标题出现，且正文中有相关内容

【排除规则】
- 不要提取仅在举例中出现的名词（如"如焦虑、抑郁等情绪问题"中的"抑郁"）
- 不要提取数字、百分比、统计值
- 不要提取文献引用（如"Smith et al., 2020"）
- 不要提取过渡句中的修饰词

【可提取的实体类型】
- concept：被定义或解释的心理学术语
- theorist：被介绍的心理学家姓名（含其主要观点）
- theory：被阐述的理论名称
- method：被说明的研究方法名称
- fact：被特别强调的、可出题的事实性内容

【输出格式】
纯 JSON 数组：
[
  {{"name": "实体名称", "type": "concept|theorist|theory|method|fact", "description": "该实体在原文中被介绍的核心内容（一句话）", "introduction_context": "原文中介绍该实体的关键句（完整引用）"}}
]

【教材内容】
{content}

【请开始提取】"""

# 单块提取提示（适配 sub_chunk 粒度）
CHUNK_EXTRACT_PROMPT = """[SYSTEM] 你是一位考研心理学辅导老师，擅长从教材中提取可出题的知识点。

【任务】从以下教材节选中提取所有【被介绍过】的知识实体。

"被介绍"的定义：该内容在文本中至少满足以下任一条件：
1. 被明确定义（如"X是指……""X是……"）
2. 被解释其特征或功能（如"X具有……特点""X表现为……"）
3. 被分类或列举（如"X包括……""X可分为……"）
4. 被赋予理论地位（如"X认为……""X提出……"）
5. 作为章节标题或小节标题出现，且正文中有相关内容

【排除规则】
- 不要提取仅在举例中出现的名词
- 不要提取数字、百分比、统计值
- 不要提取文献引用
- 不要提取过渡句中的修饰词

【可提取的实体类型】
- concept：被定义或解释的心理学术语
- theorist：被介绍的心理学家姓名
- theory：被阐述的理论名称
- method：被说明的研究方法名称
- fact：可出题的事实性内容

【输出格式】
纯 JSON 数组：
[
  {{"name": "实体名称", "type": "concept|theorist|theory|method|fact", "description": "核心内容（一句话）", "introduction_context": "原文关键句（完整引用）"}}
]

【教材节选内容】
{content}

【请开始提取】"""


def _get_llm_client():
    from openai import OpenAI

    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def _get_async_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def extract_entities(content: str) -> list[dict]:
    """同步实体提取（向后兼容），用于旧路径和关系提取器的上下文拼接。"""
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
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        logger.warning(
            "Entity extraction LLM call failed with json_object mode, "
            "retrying without: %s", e,
        )
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
                timeout=settings.graph_llm_timeout,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.choices[0].message.content or ""
        except Exception as e2:
            logger.error("Entity extraction LLM call failed (fallback as well): %s", e2)
            return []
    try:
        entities = _parse_entities(raw)
        logger.info("Entity extraction: %d entities in %.3fs", len(entities), time.monotonic() - t0)
        return entities
    except Exception as e:
        logger.error("Entity extraction parsing failed: %s", e)
        return []


def _parse_entities(raw: str) -> list[dict]:
    """从 LLM 响应中解析 JSON 实体列表。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
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
            "introduction_context": str(item.get("introduction_context", ""))[:500] if item.get("introduction_context") else "",
        })
    return validated


# ── M3.4 并行提取 ──────────────────────────────────────────────


class ParallelEntityExtractor:
    """并行实体提取器。

    流程：从 DB 读取 sub_chunks → 并行 LLM 提取 → 去重合并 → 存入 DB。
    """

    def __init__(self, max_workers: int = 3, similarity_threshold: float = 0.85):
        self.max_workers = max_workers
        self.similarity_threshold = similarity_threshold

    async def extract_from_document(
        self,
        document_id: UUID,
        task_id: Optional[UUID] = None,
    ) -> int:
        """主入口：从 DB 读取 sub_chunks，并行提取实体，去重后存入 DB。

        Args:
            document_id: 文档 UUID
            task_id: 任务 UUID（用于进度更新），可选

        Returns:
            去重后保存的实体数量
        """
        from app.database import SessionLocal
        from app.core.graph_store import delete_entities_by_document, delete_relations_by_document
        from app.core.task_manager import update_task_progress, update_task_status

        db = SessionLocal()
        try:
            # ── 1. 读取 sub_chunks（不重新分块） ──
            from app.models import SubChunk

            sub_chunks = (
                db.query(SubChunk)
                .filter(SubChunk.document_id == document_id)
                .order_by(SubChunk.chunk_index)
                .all()
            )
            if not sub_chunks:
                logger.warning("No sub_chunks found for doc %s", document_id)
                return 0

            # 清理旧实体和关系
            delete_entities_by_document(db, document_id)
            delete_relations_by_document(db, document_id)
            db.commit()

            if task_id:
                update_task_status(db, task_id, "running")
                update_task_progress(db, task_id, 0, "开始实体提取")
                db.commit()

            # ── 2. 并行提取（asyncio.Semaphore 控制并发） ──
            semaphore = asyncio.Semaphore(self.max_workers)

            async def extract_one(sc, idx: int) -> list[dict]:
                async with semaphore:
                    if task_id:
                        update_task_progress(
                            db, task_id, idx,
                            f"正在提取第 {idx + 1}/{len(sub_chunks)} 个分块...",
                        )
                        db.commit()
                    return await self._extract_chunk(sc.content, sc.chunk_index)

            tasks = [extract_one(sc, i) for i, sc in enumerate(sub_chunks)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # ── 3. 汇总，标记每个实体的来源分块 ──
            all_entities: list[dict] = []
            chunk_failures = 0
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    chunk_failures += 1
                    logger.warning("Chunk %d extraction failed: %s", i, r)
                    continue
                for ent in r:
                    ent["_chunk_index"] = i
                all_entities.extend(r)

            logger.info(
                "Parallel extraction: %d raw entities from %d chunks (%d failures)",
                len(all_entities),
                len(sub_chunks),
                chunk_failures,
            )

            # ── 4. 去重合并 ──
            deduped = self._deduplicate(all_entities)

            # ── 4.5 M3.6: 后处理筛选 ──
            from app.core.entity_filter import post_process
            deduped = post_process(deduped)

            # ── 5. 存入 DB ──
            self._save_entities(db, document_id, deduped)

            # 更新文档状态
            from datetime import datetime
            from app.models import Document

            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.lifecycle_status = "unchanged"
                doc.processed_at = datetime.utcnow()

            if task_id:
                update_task_progress(
                    db, task_id, len(sub_chunks),
                    f"提取完成，共 {len(deduped)} 个实体",
                )
            db.commit()

            logger.info(
                "Doc %s done: %d entities saved (raw=%d, deduped=%d, failed_chunks=%d)",
                document_id, len(deduped), len(all_entities), len(deduped), chunk_failures,
            )
            return len(deduped)

        except Exception as e:
            logger.error("Parallel extraction failed for doc %s: %s", document_id, e, exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()

    # ── 单块 LLM 调用 ─────────────────────────────────────────

    async def _extract_chunk(self, content: str, chunk_index: int) -> list[dict]:
        """异步提取单个 sub_chunk 的实体。"""
        client = _get_async_llm_client()
        prompt = CHUNK_EXTRACT_PROMPT.format(content=content)
        t0 = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
                timeout=settings.graph_llm_timeout,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(
                "Chunk %d LLM call failed with json_object mode, "
                "retrying without: %s", chunk_index, e,
            )
            try:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=settings.graph_llm_timeout,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                raw = response.choices[0].message.content or ""
            except Exception as e2:
                logger.error("Chunk %d LLM call failed (fallback as well): %s", chunk_index, e2)
                raise
        try:
            entities = _parse_entities(raw)
            logger.debug(
                "Chunk %d: %d entities in %.3fs",
                chunk_index, len(entities), time.monotonic() - t0,
            )
            return entities
        except Exception as e:
            logger.error("Chunk %d parsing failed: %s", chunk_index, e)
            raise

    # ── 去重 ───────────────────────────────────────────────────

    def _deduplicate(self, entities: list[dict]) -> list[dict]:
        """去重合并：按 (归一化名称, 类型) 分组，合并描述，记录分块索引。"""
        groups: dict[tuple[str, str], dict] = {}

        for ent in entities:
            norm_name = _normalize_name(ent.get("name", ""))
            if not norm_name:
                continue
            etype = ent.get("type", "concept")
            key = (norm_name, etype)

            if key in groups:
                existing = groups[key]
                # 补充更长的描述
                new_desc = ent.get("description", "")
                if len(new_desc) > len(existing.get("description", "")):
                    existing["description"] = new_desc
                # 补充更长的 introduction_context
                new_ctx = ent.get("introduction_context", "")
                if len(new_ctx) > len(existing.get("introduction_context", "")):
                    existing["introduction_context"] = new_ctx
                # 记录出现分块
                chunk_idx = ent.get("_chunk_index")
                if chunk_idx is not None:
                    occ = existing.setdefault("_occurrences", [])
                    if chunk_idx not in occ:
                        occ.append(chunk_idx)
            else:
                groups[key] = {
                    "name": ent.get("name", ""),
                    "type": etype,
                    "description": ent.get("description", ""),
                    "introduction_context": ent.get("introduction_context", ""),
                    "_occurrences": (
                        [ent["_chunk_index"]]
                        if ent.get("_chunk_index") is not None
                        else []
                    ),
                }

        # 按首次出现顺序输出
        seen_keys: list[tuple[str, str]] = []
        for ent in entities:
            key = (_normalize_name(ent.get("name", "")), ent.get("type", "concept"))
            if key not in seen_keys:
                seen_keys.append(key)

        result = []
        for key in seen_keys:
            entry = groups.get(key)
            if entry is None:
                continue
            result.append({
                "name": entry["name"],
                "type": entry["type"],
                "description": entry["description"],
                "introduction_context": entry.get("introduction_context", ""),
                "metadata": {"occurrences": entry.get("_occurrences", [])},
            })

        return result

    # ── 保存 ───────────────────────────────────────────────────

    def _save_entities(self, db, document_id: UUID, entity_list: list[dict]) -> dict[str, UUID]:
        """保存实体到 DB，包含 metadata（出现分块索引）。"""
        from app.models import Entity

        name_to_id: dict[str, UUID] = {}
        for item in entity_list:
            ent = Entity(
                document_id=document_id,
                name=item["name"],
                entity_type=item.get("type", "concept"),
                description=item.get("description", ""),
                introduction_context=item.get("introduction_context", ""),
                filter_action=item.get("filter_action", "pending"),
                filter_reason=item.get("filter_reason"),
                source=item.get("source", "llm"),
                confidence=1.0,
                extra_meta=item.get("metadata"),
            )
            db.add(ent)
            db.flush()
            name_to_id[item["name"]] = ent.id
        return name_to_id


def _normalize_name(name: str) -> str:
    """实体名称归一化：去空格、转小写（英文部分）。"""
    name = name.strip().lower()
    return re.sub(r"\s+", "", name)
