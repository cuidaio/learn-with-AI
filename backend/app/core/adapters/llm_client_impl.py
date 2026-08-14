"""
LLMClientImpl — LLMClient 接口的 OpenAI 兼容实现。

包装 openai.OpenAI SDK 的 chat.completions.create。
"""

from typing import Optional

from openai import OpenAI

from app.core.config import settings
from app.core.interfaces import LLMClient


class LLMClientImpl(LLMClient):
    """OpenAI SDK 封装。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._base_url = base_url or settings.llm_base_url
        self._api_key = api_key or settings.llm_api_key
        self._model = model or settings.llm_model
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: Optional[int] = None,
        response_format: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        kw = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if timeout is not None:
            kw["timeout"] = timeout
        if response_format is not None:
            kw["response_format"] = response_format

        response = self._client.chat.completions.create(**kw)
        return {
            "content": response.choices[0].message.content or "",
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            } if response.usage else {},
        }
