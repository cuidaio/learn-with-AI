from openai import OpenAI

from app.core.config import settings
from app.core.logging import logger

_client: OpenAI | None = None


def get_embedding_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            timeout=settings.embedding_timeout,
        )
    return _client


def reset_embedding_client() -> None:
    """重置缓存客户端，下次调用将使用新配置。"""
    global _client
    _client = None


def embed_text(text: str) -> list[float]:
    """对单段文本生成向量。"""
    client = get_embedding_client()
    try:
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dim,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding API call failed: %s", e)
        raise


def verify_embedding_dim() -> int:
    """发送测试请求，验证 dimensions 参数生效，返回实际维度。

    - 占位 / 测试 key（sk-test、sk-ci-*、sk-placeholder 等）直接跳过，不发网络请求。
    - API 不可达或响应过慢时仅警告，不阻塞启动。
    """
    key = (settings.embedding_api_key or "").strip()
    if not key or key.startswith(("sk-test", "sk-ci", "sk-placeholder")):
        logger.info(
            "Embedding dimension verification skipped (test/placeholder key), "
            "using configured default %d.",
            settings.embedding_dim,
        )
        return settings.embedding_dim

    try:
        vec = embed_text("verify")
    except Exception as e:
        logger.warning(
            "Embedding dimension verification skipped (API unreachable): %s", e
        )
        return settings.embedding_dim

    actual = len(vec)
    expected = settings.embedding_dim
    if actual == expected:
        logger.info("Embedding dimension verified: %d (matches config)", actual)
    else:
        logger.warning(
            "Embedding dimension mismatch: config=%d, API returned=%d. "
            "Check model dimensions support.",
            expected, actual,
        )
    return actual


def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量向量化。"""
    if not texts:
        return []
    client = get_embedding_client()
    try:
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
            dimensions=settings.embedding_dim,
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        logger.error("Batch embedding API call failed: %s", e)
        raise
