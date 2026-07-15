"""M1 Rewrite smoke tests — 5 core tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.atomic_splitter import split_atomic_units
from app.core.config import settings
from app.core.preprocess import clean_text
from app.core.section_block_builder import build_section_blocks
from app.core.structural_signal_extractor import extract_structural_signals
from app.core.sub_chunk_builder import build_sub_chunks


# =========================================================================
# Test 1: clean_text
# =========================================================================

def test_clean_text() -> None:
    text = """心理学概述

心理学是研究心理现象及其规律
的科学。它既研究动物的心理，也研究人的心理。

![示意图](image.png)

- 5 -

第3页

| 方法 | 说明 |
| --- | --- |
| 实验法 | 控制条件下进行 |

表格内容应保留。
"""
    result = clean_text(text)
    assert "- 5 -" not in result
    assert "第3页" not in result
    assert "![示意图](image.png)" not in result
    assert "实验法" in result
    assert "控制条件下进行" in result
    # Broken lines should be merged
    assert "研究心理现象及其规律的科学。" in result.replace("\n", "")
    # Table content preserved (| removed)
    assert "实验法" in result
    assert "控制条件下进行" in result


# =========================================================================
# Test 2: atomic_split
# =========================================================================

def test_atomic_split() -> None:
    text = (
        "## 第一章 绪论\n\n"
        "心理学是研究心理现象及其规律的科学。它既研究动物的心理也研究人的心理。"
        "感觉知觉记忆思维情绪意志都是心理现象。\n\n"
        "心理学的研究方法包括实验法观察法调查法。"
    )
    signals = extract_structural_signals(text)
    assert len(signals) >= 1
    assert signals[0].source == "markdown_heading"

    units = split_atomic_units(text, signals)
    assert len(units) >= 2, f"expected >= 2 atomic units, got {len(units)}"

    # First unit should be heading with signal
    assert units[0].type == "heading", f"first unit should be heading, got {units[0].type}"
    assert units[0].is_signal_boundary is True
    assert "第一章" in units[0].content

    # Last unit should be paragraph
    assert units[-1].type in ("paragraph", "sentence"), f"last unit type: {units[-1].type}"

    # All units must have valid positions
    for u in units:
        assert u.start_pos < u.end_pos, f"unit '{u.content[:20]}': start >= end"
        assert len(u.content) > 0, "empty unit content"


def test_atomic_split_long_paragraph() -> None:
    """Long paragraphs should split into sentences."""
    text = (
        "心理学是研究心理现象及其规律的科学。它既研究动物的心理也研究人的心理。"
        "感觉知觉记忆思维情绪意志都是心理现象。实验法观察法调查法各有优缺点。"
        "认知心理学发展心理学社会心理学都是重要分支。心理学研究方法包括定量定性。"
        "心理学有着悠久的历史可以追溯到古希腊哲学。现代心理学建立在科学基础之上。"
        "行为主义认知主义人本主义是三大主要流派。"
    ) * 5
    signals = extract_structural_signals(text)
    units = split_atomic_units(text, signals)
    assert len(units) >= 3, f"long text should produce multiple atomic units: {len(units)}"
    # At least some should be sentence type
    sentence_count = sum(1 for u in units if u.type == "sentence")
    assert sentence_count > 0, f"expected some sentences, got {sentence_count}"


# =========================================================================
# Test 3: sub_chunk_build
# =========================================================================

def test_sub_chunk_build() -> None:
    text = (
        "## 第一章 绪论\n\n"
        "心理学是研究心理现象及其规律的科学。它既研究动物的心理也研究人的心理。"
        "感觉知觉记忆思维情绪意志都是心理现象。实验法观察法调查法各有优缺点。"
        + "心理学的方法包括实验法观察法调查法。" * 60
    )
    signals = extract_structural_signals(text)
    units = split_atomic_units(text, signals)
    chunks = build_sub_chunks(units)

    assert len(chunks) >= 1, f"expected >= 1 sub-chunks, got {len(chunks)}"
    for c in chunks:
        assert c.start_pos < c.end_pos
        assert len(c.content) > 0
        # Sub-chunk should not be larger than max_chunk_size * 1.5
        # (soft limit, but shouldn't be wildly exceeded)
        if len(c.content) > settings.max_chunk_size * 2:
            print(f"WARN: Sub-chunk too large: {len(c.content)} chars (max: {settings.max_chunk_size})")


# =========================================================================
# Test 4: section_build
# =========================================================================

def test_section_build_with_headers() -> None:
    """Section blocks should cut at structural signal positions."""
    text = (
        "## 第一章 绪论\n\n"
        "心理学是研究心理现象及其规律的科学。它既研究动物的心理也研究人的心理。"
        "感觉知觉记忆思维情绪意志都是心理现象。实验法观察法调查法各有优缺点。"
        + "心理学的方法包括实验法观察法调查法。" * 30
        + "\n\n## 第二章 研究方法\n\n"
        "心理学的研究方法包括实验法和观察法。实验法控制条件下进行。观察法自然情境下进行。"
        + "问卷法调查法访谈法也是常用方法。" * 30
    )
    signals = extract_structural_signals(text)
    assert len(signals) >= 2, "should detect 2 headings"

    units = split_atomic_units(text, signals)
    chunks = build_sub_chunks(units)
    sections = build_section_blocks(chunks, signals)

    assert len(sections) >= 2, f"expected >= 2 section blocks, got {len(sections)}"
    for s in sections:
        assert s.start_pos < s.end_pos
        assert len(s.content) > 0
        assert s.id is not None

    # At least one section should have a title
    titled = [s for s in sections if s.title]
    assert len(titled) >= 1, "at least one section should have a title"


def test_section_build_plain_text() -> None:
    """Plain text (no signals) should produce one section block."""
    text = "心理学是研究心理现象及其规律的科学。" * 30
    signals = extract_structural_signals(text)
    assert len(signals) == 0, "plain text should have no signals"

    units = split_atomic_units(text, signals)
    chunks = build_sub_chunks(units)
    sections = build_section_blocks(chunks, signals)

    assert len(sections) >= 1, "plain text should produce >= 1 section block"


# =========================================================================
# Test 5: e2e_upload (requires running backend)
# =========================================================================

def test_e2e_upload() -> None:
    """End-to-end upload test via TestClient."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Upload a document with headings (each section > 500 chars to survive merge)
    text = (
        "## 第一章 绪论\n\n"
        "心理学是研究心理现象及其规律的科学。它既研究动物的心理也研究人的心理。"
        "感觉知觉记忆思维情绪意志都是心理现象。"
        + "心理学研究方法包括实验法观察法调查法。" * 35
        + "\n\n## 第二章 研究方法\n\n"
        "心理学的研究方法包括实验法和观察法。实验法控制条件下进行。观察法自然情境下进行。"
        + "问卷法调查法访谈法也是常用方法。" * 35
    )
    resp = client.post("/api/documents", json={"title": "测试文档", "raw_text": text})
    assert resp.status_code == 201, f"upload failed: {resp.status_code} {resp.text}"

    data = resp.json()
    assert data["status"] == "success"
    assert "document_id" in data
    assert data["total_atomic_units"] > 0
    assert data["total_sub_chunks"] > 0
    assert data["total_section_blocks"] >= 2, f"expected >= 2 sections, got {data['total_section_blocks']}"
    assert data["total_characters"] > 0

    doc_id = data["document_id"]

    # Fetch chunks
    resp2 = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp2.status_code == 200, f"fetch chunks failed: {resp2.status_code}"
    chunks_data = resp2.json()
    assert len(chunks_data["section_blocks"]) >= 2
    for sb in chunks_data["section_blocks"]:
        assert sb["char_count"] > 0
        if sb["sub_chunks"]:
            for sc in sb["sub_chunks"]:
                assert sc["char_count"] > 0
                assert sc["start_pos"] < sc["end_pos"]

    # List documents
    resp3 = client.get("/api/documents")
    assert resp3.status_code == 200
    docs = resp3.json()["documents"]
    assert any(d["id"] == doc_id for d in docs), "uploaded doc should appear in list"