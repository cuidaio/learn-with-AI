"""M2 RAG tests — 4 tests per dev_plan."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.prompts import build_user_prompt, USER_PROMPT_TEMPLATE


# =========================================================================
# Test 1: prompt structural test (no backend needed)
# =========================================================================

def test_prompt_context_before_question() -> None:
    """验证 User Prompt 模板中，参考资料在问题之前。"""
    prompt = build_user_prompt("【1】test reference content", "test question")
    ref_idx = prompt.index("### 参考资料")
    q_idx = prompt.index("### 问题")
    assert ref_idx < q_idx, "参考资料必须在问题之前"


# =========================================================================
# Tests 2-5: integration tests via TestClient (requires running backend)
# =========================================================================

def test_ask_returns_answer_with_citations() -> None:
    """上传文档 → 提问 → 验证 answer 包含【来源编号】引用。"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    text = (
        "## 青春期自我意识\n\n"
        "青春期是自我意识发展的第二个飞跃期。此时个体内心世界日益丰富，开始频繁内省。"
        "自我意识的分化是青春期的重要特征。主观的我和客观的我开始分离。"
        + "青春期自我意识发展迅速、自我评价能力提高。" * 30
    )
    resp = client.post("/api/documents", json={"title": "青春期", "raw_text": text})
    assert resp.status_code == 201, f"upload failed: {resp.text}"
    doc_id = resp.json()["document_id"]

    resp2 = client.post("/api/ask", json={
        "document_id": doc_id,
        "question": "青春期自我意识有什么特点？",
        "top_k": 3,
    })
    assert resp2.status_code == 200, f"ask failed: {resp2.text}"
    data = resp2.json()

    assert "answer" in data
    assert len(data["answer"]) > 0
    assert any(s["cited_in_answer"] for s in data["sources"]), \
        "at least one source should be cited in answer"


def test_ask_sources_ordered_by_relevance() -> None:
    """验证返回的 sources 按 relevance_score 降序排列。"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    text = (
        "## 第一章 认知发展\n\n"
        "皮亚杰认为认知发展分为四个阶段。感知运动阶段是0-2岁。"
        "前运算阶段是2-7岁。具体运算阶段是7-11岁。形式运算阶段是11岁以上。"
        + "认知发展阶段理论影响深远、被广泛研究。" * 30
        + "\n\n## 第二章 语言发展\n\n"
        "语言发展包括语音语义语法语用四个方面。婴幼儿在1岁左右开始说出第一个词。"
        + "语言发展有关键期、敏感期。" * 30
    )
    resp = client.post("/api/documents", json={"title": "发展心理学", "raw_text": text})
    assert resp.status_code == 201, f"upload failed: {resp.text}"
    doc_id = resp.json()["document_id"]

    resp2 = client.post("/api/ask", json={
        "document_id": doc_id,
        "question": "皮亚杰的认知发展阶段包括哪些？",
        "top_k": 3,
    })
    assert resp2.status_code == 200, f"ask failed: {resp2.text}"
    data = resp2.json()

    scores = [s["relevance_score"] for s in data["sources"]]
    assert scores == sorted(scores, reverse=True), \
        f"sources should be descending by relevance: {scores}"


def test_ask_handles_out_of_context() -> None:
    """提问教材中不存在的内容 → 返回'教材中未涉及该内容'。"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    text = (
        "## 青春期自我意识\n\n"
        "青春期是自我意识发展的第二个飞跃期。"
        + "自我意识发展迅速、自我评价能力提高。" * 30
    )
    resp = client.post("/api/documents", json={"title": "青春期", "raw_text": text})
    assert resp.status_code == 201, f"upload failed: {resp.text}"
    doc_id = resp.json()["document_id"]

    # 提问完全不相关的内容
    resp2 = client.post("/api/ask", json={
        "document_id": doc_id,
        "question": "量子力学的基本原理是什么？薛定谔方程怎么解？",
        "top_k": 3,
    })
    assert resp2.status_code == 200, f"ask failed: {resp2.text}"
    data = resp2.json()
    assert "教材中未涉及该内容" in data["answer"], \
        f"expected out-of-context message, got: {data['answer'][:100]}"


def test_ask_document_not_found() -> None:
    """不存在的 document_id → 404。"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/ask", json={
        "document_id": "00000000-0000-0000-0000-000000000000",
        "question": "测试问题",
        "top_k": 3,
    })
    assert resp.status_code == 404
