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
    # M3
    folder_id: UUID | None = None
    position: int = 0
    user_title: str | None = None

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    title: str | None = None
    folder_id: UUID | None = None
    position: int | None = None
    user_title: str | None = None


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
    # M3.6
    introduction_context: str | None = None
    filter_action: str = "pending"
    filter_reason: str | None = None
    source: str = "llm"
    # M3.7
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class EntityListResponse(BaseModel):
    entities: list[EntityItem]
    total: int
    filters: dict


class EntityUpdateRequest(BaseModel):
    name: str | None = None
    entity_type: str | None = None
    description: str | None = None
    introduction_context: str | None = None
    filter_action: str | None = None  # "keep" | "review" | "discard"


class EntityReviewRequest(BaseModel):
    action: str  # "keep" | "discard"


class EntityManualCreate(BaseModel):
    document_id: UUID
    name: str
    entity_type: str = "concept"
    description: str = ""
    introduction_context: str = ""


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


# ── Folders (M3) ──────────────────────────────────────────────────────────

class FolderCreate(BaseModel):
    name: str = Field(..., max_length=255)
    parent_id: UUID | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    parent_id: UUID | None = None
    position: int | None = None


class FolderResponse(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    position: int = 0
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]


# ── Learning Events (M3) ──────────────────────────────────────────────────

class LearningEventCreate(BaseModel):
    event_type: str = Field(..., max_length=30)
    document_id: UUID | None = None
    entity_id: UUID | None = None
    question_id: UUID | None = None
    context: dict | None = None


class LearningEventResponse(BaseModel):
    id: UUID
    event_type: str
    document_id: UUID | None = None
    entity_id: UUID | None = None
    question_id: UUID | None = None
    context: dict | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ── Document Highlight (M3) ──────────────────────────────────────────────

class HighlightItem(BaseModel):
    entity_name: str
    entity_type: str
    start: int
    end: int


class DocumentHighlightResponse(BaseModel):
    document_id: UUID
    title: str
    content: str
    highlights: list[HighlightItem]


# ── Task Card (M3) ────────────────────────────────────────────────────────

class TaskCardItem(BaseModel):
    task_id: UUID
    task_type: str
    status: str
    card_title: str | None = None
    card_icon: str | None = None
    result_content_type: str | None = None
    is_default: bool = False
    progress: int = 0
    progress_text: str | None = None
    params: dict | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class TaskCardListResponse(BaseModel):
    tasks: list[TaskCardItem]


class GraphTaskResponse(BaseModel):
    task_id: UUID
    status: str


# ── Graph Neighbors & Path (M3.9) ─────────────────────────────────────────

class NeighborEntityItem(BaseModel):
    id: UUID
    name: str
    entity_type: str | None = None
    score: float = 0.0


class NeighborRelationItem(BaseModel):
    id: UUID
    relation_type: str
    description: str | None = None
    source_entity_id: UUID | None = None
    target_entity_id: UUID | None = None


class NeighborItem(BaseModel):
    entity: NeighborEntityItem
    relation: NeighborRelationItem


class NeighborsResponse(BaseModel):
    entity: NeighborEntityItem
    neighbors: list[NeighborItem]
    has_more: bool = False
    total_count: int = 0


class RelationManualCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str = "related_to"
    description: str = ""


class RelationManualCreateResponse(BaseModel):
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str


class RelationManualUpdate(BaseModel):
    relation_type: str | None = None
    description: str | None = None


class PathEdgeItem(BaseModel):
    relation_id: UUID | None = None
    from_id: UUID
    to_id: UUID
    label: str


class PathResponse(BaseModel):
    path: list[UUID]
    edges: list[PathEdgeItem]
    text: str


# ── App Config (M3.11) ───────────────────────────────────────────────────────

class AppConfigUpdate(BaseModel):
    """前端提交的配置更新。"""
    embedding: dict | None = None
    llm: dict | None = None


class ConfigTestRequest(BaseModel):
    """测试连接请求。"""
    type: str  # "embedding" | "llm"
    base_url: str
    api_key: str
    model: str


class ConfigTestResponse(BaseModel):
    """测试连接响应。"""
    success: bool
    latency: float | None = None
    error: str | None = None