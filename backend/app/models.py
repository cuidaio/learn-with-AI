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
    """M2.8.2 异步任务 — 出题/组卷/批改的统一任务表。"""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(20), nullable=False)        # question_generation
    status = Column(String(20), default="pending")        # pending|running|completed|failed

    params = Column(JSONB, nullable=False)                 # 任务参数
    result = Column(JSONB, nullable=True)                  # completed 时存放结果
    error_message = Column(Text, nullable=True)            # failed 时存放错误信息

    # 进度追踪
    total_steps = Column(Integer, nullable=True)
    completed_steps = Column(Integer, default=0)
    current_step_description = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    extra_meta = Column("metadata", JSONB, default=dict)


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
