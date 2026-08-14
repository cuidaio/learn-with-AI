"""
M3.11: API 配置管理路由。
提供配置的读取、更新、测试连接、重置功能。
"""

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import OpenAI, AuthenticationError, APIConnectionError, APIStatusError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.schemas import AppConfigUpdate, ConfigTestRequest, ConfigTestResponse

router = APIRouter(prefix="/api/config", tags=["config"])

# ── 帮助函数 ─────────────────────────────────────────────────────────────────


def _mask_api_key(key: str) -> str:
    """脱敏 API Key，保留首尾各 4 字符。"""
    if not key or len(key) < 12:
        return "***"
    return key[:4] + "****" + key[-4:]


def _get_config_from_db(db: Session) -> dict:
    """从 app_config 表读取所有配置项，返回 {key: value} 字典。"""
    rows = db.execute(text("SELECT key, value FROM app_config")).fetchall()
    config = {}
    for row in rows:
        config[row.key] = dict(row.value)
    return config


def _load_config_to_settings(db: Session) -> None:
    """从数据库加载配置，覆盖 settings 对象。"""
    config = _get_config_from_db(db)
    embedding = config.get("embedding", {})
    llm = config.get("llm", {})
    if embedding.get("api_key"):
        settings.embedding_api_key = embedding["api_key"]
        settings.embedding_base_url = embedding.get("base_url", settings.embedding_base_url)
        settings.embedding_model = embedding.get("model", settings.embedding_model)
    if llm.get("api_key"):
        settings.llm_api_key = llm["api_key"]
        settings.llm_base_url = llm.get("base_url", settings.llm_base_url)
        settings.llm_model = llm.get("model", settings.llm_model)


def _reset_cached_clients() -> None:
    """重置已缓存的外部客户端，使下一次调用使用新配置。"""
    from app.core.embeddings import reset_embedding_client
    reset_embedding_client()


def _upsert_config(db: Session, key: str, value: dict) -> None:
    """Upsert a config row using raw SQL with JSON serialization."""
    db.execute(
        text("""
            INSERT INTO app_config (key, value, updated_at)
            VALUES (:key, CAST(:value AS JSONB), NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = CAST(:value AS JSONB),
                updated_at = NOW()
        """),
        {"key": key, "value": json.dumps(value)},
    )


# ── 初始化入口（由 main.py lifespan 调用） ────────────────────────────────────


def init_config_from_db(db: Session) -> None:
    """启动时从数据库加载配置到 settings。"""
    try:
        _load_config_to_settings(db)
    except Exception:
        # 表可能尚未创建，静默忽略
        pass


# ── API 端点 ─────────────────────────────────────────────────────────────────


@router.get("")
def get_config(db: Session = Depends(get_db)) -> dict:
    """获取当前配置，API Key 脱敏。"""
    config = _get_config_from_db(db)
    result = {}
    for key, value in config.items():
        entry = dict(value)
        if "api_key" in entry and entry["api_key"]:
            entry["api_key"] = _mask_api_key(entry["api_key"])
        result[key] = entry
    return result


@router.put("")
def update_config(body: AppConfigUpdate, db: Session = Depends(get_db)) -> dict:
    """更新配置并同步到内存中的 settings。"""
    updates = {}

    if body.embedding is not None:
        key = body.embedding.get("api_key", "")
        updates["embedding"] = body.embedding
        if key:
            settings.embedding_api_key = key
        if body.embedding.get("base_url"):
            settings.embedding_base_url = body.embedding["base_url"]
        if body.embedding.get("model"):
            settings.embedding_model = body.embedding["model"]

    if body.llm is not None:
        key = body.llm.get("api_key", "")
        updates["llm"] = body.llm
        if key:
            settings.llm_api_key = key
        if body.llm.get("base_url"):
            settings.llm_base_url = body.llm["base_url"]
        if body.llm.get("model"):
            settings.llm_model = body.llm["model"]

    # 持久化到数据库
    for key, value in updates.items():
        _upsert_config(db, key, value)
    db.commit()

    # 重置客户端缓存使新配置立即生效
    _reset_cached_clients()

    return {"status": "ok", "message": "配置已更新"}


@router.post("/test", response_model=ConfigTestResponse)
def test_connection(body: ConfigTestRequest) -> ConfigTestResponse:
    """测试指定配置的连接可用性。"""
    start = time.time()
    try:
        client = OpenAI(
            api_key=body.api_key,
            base_url=body.base_url,
            timeout=15,
        )
        if body.type == "embedding":
            client.embeddings.create(
                model=body.model,
                input="test",
            )
        elif body.type == "llm":
            client.chat.completions.create(
                model=body.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
        else:
            return ConfigTestResponse(success=False, error=f"Unknown type: {body.type}")
        latency = round(time.time() - start, 2)
        return ConfigTestResponse(success=True, latency=latency)
    except Exception as e:
        return ConfigTestResponse(success=False, error=str(e))


@router.get("/models")
def get_models(
    type: str = Query(...),
    base_url: str = Query(...),
    api_key: str = Query(...),
) -> dict:
    """获取指定平台支持的模型列表。"""
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="Base URL 和 API Key 不能为空")
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=15)
    try:
        response = client.models.list()
        models = sorted([m.id for m in response.data])
        return {"models": models}
    except AuthenticationError:
        raise HTTPException(status_code=400, detail="API Key 无效，请检查后重试")
    except APIConnectionError:
        raise HTTPException(status_code=400, detail="无法连接到服务器，请检查 Base URL")
    except APIStatusError:
        raise HTTPException(status_code=400, detail="该平台不支持模型列表查询，请手动输入")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取模型列表失败: {str(e)}")


@router.post("/reset")
def reset_config(db: Session = Depends(get_db)) -> dict:
    """重置所有配置为系统默认值。"""
    defaults = {
        "embedding": {
            "base_url": "https://api.siliconflow.cn/v1/",
            "api_key": "",
            "model": "Qwen/Qwen3-Embedding-4B",
        },
        "llm": {
            "base_url": "https://api.deepseek.com/v1/",
            "api_key": "",
            "model": "deepseek-v4-flash",
        },
    }
    for key, value in defaults.items():
        _upsert_config(db, key, value)
    db.commit()

    # 同步到内存
    settings.embedding_api_key = ""
    settings.embedding_base_url = defaults["embedding"]["base_url"]
    settings.embedding_model = defaults["embedding"]["model"]
    settings.llm_api_key = ""
    settings.llm_base_url = defaults["llm"]["base_url"]
    settings.llm_model = defaults["llm"]["model"]

    _reset_cached_clients()

    return {"status": "ok", "message": "配置已重置为默认值"}
