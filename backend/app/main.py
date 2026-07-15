from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import Base, engine, init_db
from app.routes import ask, ask_stream, documents, graph, questions, tasks
from app.schemas import HealthResponse, MessageResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.log_config()
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
app.include_router(graph.router)
app.include_router(questions.router)
app.include_router(tasks.router)


@app.get("/", response_model=MessageResponse)
def root() -> MessageResponse:
    return MessageResponse(message="learn-with-AI backend is running", status="ok")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


# 前端 proxy 不 rewrite /api/health，所以后端需要额外挂一个
app.add_api_route("/api/health", health, response_model=HealthResponse, methods=["GET"])
