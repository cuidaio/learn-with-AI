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
        )
    return _client


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
    """发送测试请求，验证 dimensions 参数生效，返回实际维度。"""
    vec = embed_text("verify")
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
