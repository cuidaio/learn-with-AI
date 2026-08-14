from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # ── 旧兼容配置（通用回退） ──────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = ""

    # ── Embedding 独立配置 ─────────────────────────────────
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "Qwen/Qwen3-Embedding-4B"
    embedding_dim: int = 1024
    embedding_timeout: int = 10          # Embedding API 单次调用超时（秒）

    # ── LLM 独立配置 ──────────────────────────────────────
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "deepseek-ai/DeepSeek-V4-Flash"

    # ── 分块参数（软目标，非硬约束） ──────────────────────
    chunk_size: int = 800             # 子块目标大小
    min_chunk_size: int = 200         # 子块尽量不小于此值
    max_chunk_size: int = 1500        # 子块尽量不超过此值
    section_min_chars: int = 500      # 章节块尽量不小于此值
    section_max_chars: int = 3000     # 章节块尽量不超过此值
    paragraph_split_chars: int = 300  # 段落超过此长度拆分为句子

    # ── 实体提取并行配置（M3.4） ──────────────────────────
    entity_extraction_workers: int = 3          # 并行提取并发数
    entity_extraction_similarity_threshold: float = 0.85  # 去重相似度阈值

    # ── 实体筛选配置（M3.6） ────────────────────────────
    entity_filter_enabled: bool = True           # 是否启用后处理筛选

    # ── 知识图谱配置（M2.8） ──────────────────────────────
    graph_extraction_batch_size: int = 10
    graph_min_confidence: float = 0.6
    graph_max_entities_per_doc: int = 50
    graph_max_relations_per_doc: int = 80
    graph_llm_timeout: int = 180          # 知识图谱 LLM 调用超时（秒）

    # ── 出题配置（M2.8.2） ──────────────────────────────
    question_workers: int = 3             # 并行出题最大并发数
    question_timeout: int = 120           # 单实体 LLM 调用超时（秒）

    @model_validator(mode="after")
    def _backward_compat(self) -> "Settings":
        """旧 OPENAI_* 配置自动回填到新字段。"""
        if self.openai_base_url:
            if not self.embedding_base_url:
                self.embedding_base_url = self.openai_base_url
                self.embedding_api_key = self.openai_api_key
            if not self.llm_base_url:
                self.llm_base_url = self.openai_base_url
                self.llm_api_key = self.openai_api_key
        return self

    def log_config(self) -> None:
        """脱敏打印当前配置状态。"""
        from app.core.logging import logger

        def _mask(key: str) -> str:
            if not key or len(key) < 8:
                return "***"
            return key[:4] + "****" + key[-4:]

        logger.info(
            "Embedding: base_url=%s model=%s api_key=%s",
            self.embedding_base_url,
            self.embedding_model,
            _mask(self.embedding_api_key),
        )
        logger.info(
            "LLM: base_url=%s model=%s api_key=%s",
            self.llm_base_url,
            self.llm_model,
            _mask(self.llm_api_key),
        )


settings = Settings()
