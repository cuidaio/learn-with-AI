import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=False)
    cleaned_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_atomic_units = Column(Integer, default=0)
    total_sub_chunks = Column(Integer, default=0)
    total_section_blocks = Column(Integer, default=0)
    lifecycle_status = Column(String(20), default="new")
    processed_at = Column(DateTime, nullable=True)
    # M3: 文件夹 + 排序 + 自定义标题
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, default=0)
    user_title = Column(String(255), nullable=True)

    section_blocks = relationship("SectionBlock", back_populates="document", cascade="all, delete-orphan")
    sub_chunks = relationship("SubChunk", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    relations = relationship("Relation", back_populates="document", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_meta = Column("metadata", JSONB, default=dict)

    # M3.6: 被介绍上下文 + 筛选状态
    introduction_context = Column(Text, nullable=True)
    filter_action = Column(String(20), default="pending")   # pending|keep|review|discard
    filter_reason = Column(String(100), nullable=True)
    filter_metadata = Column(JSONB, default=dict)
    source = Column(String(20), default="llm")              # llm|manual

    document = relationship("Document", back_populates="entities")


class Relation(Base):
    __tablename__ = "relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_meta = Column("metadata", JSONB, default=dict)

    document = relationship("Document", back_populates="relations")


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_node_id = Column(UUID(as_uuid=True), nullable=True)
    question_type = Column(String(20), nullable=False)   # fill|short_answer|essay|choice|multi_choice
    stem = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    options = Column(JSONB, nullable=True)                # M2.8.2: 选择题选项 {"A": "选项1", ...}
    explanation = Column(Text, nullable=True)
    bloom_level = Column(String(20), nullable=True)
    difficulty_estimate = Column(Float, nullable=True)
    difficulty_calibrated = Column(Float, nullable=True)
    source_entity_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    source_text_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_meta = Column("metadata", JSONB, default=dict)

    document = relationship("Document", back_populates="questions")


class Task(Base):
    """M2.8.2 异步任务 — 出题/组卷/批改的统一任务表。M3: 添加卡片字段。"""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(20), nullable=False)        # question_generation | graph_generation
    status = Column(String(20), default="pending")        # pending|running|completed|failed

    params = Column(JSONB, nullable=False)                 # 任务参数
    result = Column(JSONB, nullable=True)                  # completed 时存放结果
    error_message = Column(Text, nullable=True)            # failed 时存放错误信息

    # 进度追踪
    total_steps = Column(Integer, nullable=True)
    completed_steps = Column(Integer, default=0)
    current_step_description = Column(Text, nullable=True)

    # M3: 卡片字段
    card_title = Column(String(255), nullable=True)
    card_icon = Column(String(50), nullable=True)
    result_content_type = Column(String(50), nullable=True)  # document|chat|entities|questions|knowledge_graph
    is_default = Column(Integer, default=0)                   # 0/1
    progress = Column(Integer, default=0)                     # 0-100
    progress_text = Column(String(255), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    extra_meta = Column("metadata", JSONB, default=dict)


class Folder(Base):
    """M3: 文件夹。"""
    __tablename__ = "folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    parent_id = Column(UUID(as_uuid=True), nullable=True)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearningEvent(Base):
    """M3: 学习事件埋点。"""
    __tablename__ = "learning_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(30), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    sub_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    question_id = Column(UUID(as_uuid=True), nullable=True)
    context = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubChunk(Base):
    __tablename__ = "sub_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    start_pos = Column(Integer, nullable=False)
    end_pos = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.embedding_dim), nullable=True)
    extra_meta = Column("metadata", JSONB, default=dict)

    document = relationship("Document", back_populates="sub_chunks")


class SectionBlock(Base):
    __tablename__ = "section_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    start_pos = Column(Integer, nullable=False)
    end_pos = Column(Integer, nullable=False)
    block_index = Column(Integer, nullable=False)
    title = Column(Text, nullable=True)
    sub_chunk_ids = Column(JSONB, default=list)
    extra_meta = Column("metadata", JSONB, default=dict)

    document = relationship("Document", back_populates="section_blocks")
