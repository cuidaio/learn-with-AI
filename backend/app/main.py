from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import Base, engine, init_db
from app.core.di_container import init_container
from app.routes import ask, ask_stream, config, documents, entities, folders, graph, learning_events, questions, tasks
from app.schemas import HealthResponse, MessageResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.log_config()

    # M3.3: 初始化 DI 容器，注入依赖到 TaskManager
    container = init_container()
    from app.core.task_manager import configure_task_manager

    configure_task_manager(
        task_factory=container.get_task_factory(),
        task_store=container.get_task_store(),
    )

    # M3.11: 从数据库加载持久化配置，覆盖 .env 默认值
    from app.database import SessionLocal
    from app.routes.config import init_config_from_db
    db = SessionLocal()
    try:
        init_config_from_db(db)
        settings.log_config()
    finally:
        db.close()

    yield


app = FastAPI(title="learn-with-AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(ask_stream.router)
app.include_router(entities.router)
app.include_router(folders.router)
app.include_router(graph.router)
app.include_router(graph.graph_browser_router)
app.include_router(learning_events.router)
app.include_router(questions.router)
app.include_router(tasks.router)
app.include_router(config.router)


@app.get("/", response_model=MessageResponse)
def root() -> MessageResponse:
    return MessageResponse(message="learn-with-AI backend is running", status="ok")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


# 前端 proxy 不 rewrite /api/health，所以后端需要额外挂一个
app.add_api_route("/api/health", health, response_model=HealthResponse, methods=["GET"])
