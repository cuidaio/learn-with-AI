"""
EmbeddingClientImpl — EmbeddingClient 接口的 OpenAI 兼容实现。

包装 app.core.embeddings.embed_text。
"""

from app.core.embeddings import embed_text as _embed_text
from app.core.interfaces import EmbeddingClient


class EmbeddingClientImpl(EmbeddingClient):
    """现有 embed_text 函数的接口包装。"""

    def embed(self, text: str) -> list[float]:
        return _embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_embed_text(t) for t in texts]
