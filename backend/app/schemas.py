from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Common ────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str
    status: str


# ── Document ──────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str = Field("", max_length=255)
    raw_text: str = Field(..., min_length=1)


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    status: str = "completed"
    total_characters: int = 0
    total_atomic_units: int = 0
    total_sub_chunks: int = 0
    total_section_blocks: int = 0
    lifecycle_status: str = "new"
    processed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    status: str
    document_id: UUID
    title: str
    total_atomic_units: int
    total_sub_chunks: int
    total_section_blocks: int
    total_characters: int


# ── Chunks ────────────────────────────────────────────────────────────────

class SubChunkItem(BaseModel):
    chunk_index: int
    content: str
    char_count: int
    start_pos: int
    end_pos: int


class SectionBlockItem(BaseModel):
    block_index: int
    title: str | None
    level: int = 0
    level_type: str = "semantic"
    content: str
    char_count: int
    sub_chunks: list[SubChunkItem] = []

    class Config:
        from_attributes = True


class ChunkDetailResponse(BaseModel):
    document_id: UUID
    title: str
    section_blocks: list[SectionBlockItem]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


# ── Ask / RAG ───────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    document_ids: list[UUID] = Field(default_factory=list, description="文档 UUID 列表（多文档）")
    document_id: UUID | None = Field(default=None, description="（向后兼容）单文档 UUID")
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    top_k: int = Field(5, ge=1, le=20, description="检索命中的子块数量")


class SourceItem(BaseModel):
    document_title: str | None = None
    section_title: str | None = None
    relevance_score: float = 0.0
    cited_in_answer: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = []


# ── Knowledge Graph (M2.8) ────────────────────────────────────────────────

class EntityItem(BaseModel):
    id: UUID
    name: str
    entity_type: str | None = None
    description: str | None = None
    confidence: float = 1.0

    class Config:
        from_attributes = True


class RelationItem(BaseModel):
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    description: str | None = None
    source_name: str = ""
    target_name: str = ""

    class Config:
        from_attributes = True


class KnowledgeGraphResponse(BaseModel):
    document_id: UUID
    document_title: str
    entities: list[EntityItem]
    relations: list[RelationItem]


# ── Questions (M2.8) ──────────────────────────────────────────────────────

class QuestionGenerateRequest(BaseModel):
    document_id: UUID
    entity_ids: list[UUID] | None = None
    types: list[str] | None = None
    count_per_type: int = 3


class QuestionItem(BaseModel):
    id: UUID
    question_type: str
    stem: str
    answer: str
    options: dict | None = None
    explanation: str | None = None
    bloom_level: str | None = None
    difficulty_estimate: float | None = None
    source_entity_ids: list[UUID] | None = None

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    document_id: UUID
    questions: list[QuestionItem]


# ── Tasks (M2.8.2) ─────────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    document_id: UUID
    entity_ids: list[UUID]
    total_count: int = 18
    types: list[str] = Field(
        default_factory=lambda: ["choice", "multi_choice", "fill", "short_answer", "essay"],
    )
    type_weights: dict[str, float] | None = None
    scenario: str = "section_review"

    @field_validator("total_count")
    @classmethod
    def total_count_range(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("total_count must be between 1 and 100")
        return v

    @field_validator("types")
    @classmethod
    def valid_types(cls, v: list[str]) -> list[str]:
        valid = {"choice", "multi_choice", "fill", "short_answer", "essay"}
        for t in v:
            if t not in valid:
                raise ValueError(f"Invalid type: {t}")
        return v


class TaskCreateResponse(BaseModel):
    task_id: UUID
    status: str


class TaskStatusResponse(BaseModel):
    task_id: UUID
    status: str
    total_steps: int | None = None
    completed_steps: int = 0
    current_step: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class TaskResultResponse(BaseModel):
    task_id: UUID
    status: str
    result: dict | None = None


class TaskItem(BaseModel):
    task_id: UUID
    task_type: str
    status: str
    total_steps: int | None = None
    completed_steps: int = 0
    current_step: str | None = None
    params: dict | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskItem]