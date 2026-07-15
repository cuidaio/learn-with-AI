"""
Document routes — M1 Rewrite: 5-stage pipeline.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.atomic_splitter import split_atomic_units
from app.core.embeddings import embed_text
from app.core.logging import logger
from app.core.preprocess import clean_text
from app.core.section_block_builder import build_section_blocks
from app.core.structural_signal_extractor import extract_structural_signals
from app.core.sub_chunk_builder import build_sub_chunks
from app.database import get_db
from app.models import Document, SectionBlock, SubChunk
from app.schemas import (
    ChunkDetailResponse,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    SectionBlockItem,
    SubChunkItem,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _run_graph_build_async(document_id: uuid.UUID) -> None:
    """后台分阶段构建图谱（独立 DB session）。

    阶段1：实体提取 → commit → 前端可见
    阶段2：关系提取 → commit（依赖阶段1的实体）
    """
    from app.database import SessionLocal
    from app.core.graph_builder import extract_and_save_entities, extract_and_save_relations

    db = SessionLocal()
    try:
        has_entities = extract_and_save_entities(db, document_id)
        if has_entities:
            extract_and_save_relations(db, document_id)
    except Exception:
        logger.warning("Async graph build failed", exc_info=True)
    finally:
        db.close()


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        total_characters=len(doc.raw_text or ""),
        total_atomic_units=doc.total_atomic_units or 0,
        total_sub_chunks=doc.total_sub_chunks or 0,
        total_section_blocks=doc.total_section_blocks or 0,
        created_at=doc.created_at,
    )


# ── POST /api/documents ───────────────────────────────────────────────────


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def upload_document(payload: DocumentCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw_text = payload.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text cannot be empty")

    doc_id = uuid.uuid4()
    title = payload.title or raw_text[:60]

    # Stage 1: clean
    cleaned = clean_text(raw_text)
    if not cleaned:
        raise HTTPException(status_code=400, detail="No valid content after cleaning")

    doc = Document(
        id=doc_id, title=title, raw_text=raw_text, cleaned_text=cleaned,
    )
    db.add(doc)
    db.flush()  # flush to make id visible for FK checks in same transaction

    try:
        # Stage 2: extract structural signals
        signals = extract_structural_signals(cleaned)
        logger.info("Stage 2: %d structural signals", len(signals))

        # Stage 3: split atomic units
        atomic_units = split_atomic_units(cleaned, signals)
        logger.info("Stage 3: %d atomic units", len(atomic_units))

        if not atomic_units:
            raise HTTPException(status_code=400, detail="No atomic units produced")

        # Stage 4: build sub-chunks
        sub_chunks = build_sub_chunks(atomic_units)
        logger.info("Stage 4: %d sub-chunks", len(sub_chunks))

        # Stage 5: build section blocks
        section_blocks = build_section_blocks(sub_chunks, signals)
        logger.info("Stage 5: %d section blocks", len(section_blocks))

        # Persist sub-chunks with embeddings
        sub_chunk_rows: list[SubChunk] = []
        for sc in sub_chunks:
            embedding = None
            try:
                embedding = embed_text(sc.content)
            except Exception as e:
                logger.warning("Embedding failed for sub-chunk %d: %s", sc.chunk_index, e)

            row = SubChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                content=sc.content,
                start_pos=sc.start_pos,
                end_pos=sc.end_pos,
                chunk_index=sc.chunk_index,
                embedding=embedding,
                extra_meta={"source": sc.source},
            )
            db.add(row)
            db.flush()
            sub_chunk_rows.append(row)

        # Persist section blocks (store sub-chunk UUIDs)
        for sb in section_blocks:
            sc_uuid_strs = [str(sub_chunk_rows[i].id) for i in sb.sub_chunk_indices if i < len(sub_chunk_rows)]
            row = SectionBlock(
                id=uuid.uuid4(),
                document_id=doc_id,
                content=sb.content,
                start_pos=sb.start_pos,
                end_pos=sb.end_pos,
                block_index=sb.block_index,
                title=sb.title,
                sub_chunk_ids=sc_uuid_strs,
                extra_meta=sb.metadata,
            )
            db.add(row)

        # Update document stats
        doc.total_atomic_units = len(atomic_units)
        doc.total_sub_chunks = len(sub_chunks)
        doc.total_section_blocks = len(section_blocks)
        doc.lifecycle_status = "new"
        db.commit()

        # M2.8: 后台异步知识图谱构建（不阻塞上传响应）
        background_tasks.add_task(_run_graph_build_async, doc_id)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error("Document processing failed: %s", e)
        db.rollback()
        raise HTTPException(status_code=503, detail=f"Processing failed: {str(e)}")

    return DocumentUploadResponse(
        status="success",
        document_id=doc.id,
        title=doc.title,
        total_atomic_units=doc.total_atomic_units or 0,
        total_sub_chunks=doc.total_sub_chunks or 0,
        total_section_blocks=doc.total_section_blocks or 0,
        total_characters=len(doc.raw_text),
    )


# ── GET /api/documents ────────────────────────────────────────────────────


@router.get("", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(documents=[_doc_to_response(d) for d in docs])


# ── GET /api/documents/{id}/chunks ────────────────────────────────────────


@router.get("/{id}/chunks", response_model=ChunkDetailResponse)
def get_document_chunks(id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    sections = (
        db.query(SectionBlock)
        .filter(SectionBlock.document_id == id)
        .order_by(SectionBlock.block_index)
        .all()
    )

    # Build sub-chunk lookup
    sub_chunks = (
        db.query(SubChunk)
        .filter(SubChunk.document_id == id)
        .order_by(SubChunk.chunk_index)
        .all()
    )
    sc_map = {str(sc.id): sc for sc in sub_chunks}

    return ChunkDetailResponse(
        document_id=doc.id,
        title=doc.title,
        section_blocks=[
            SectionBlockItem(
                block_index=s.block_index,
                title=s.title,
                level=0,
                level_type="semantic",
                content=s.content,
                char_count=len(s.content),
                sub_chunks=[
                    SubChunkItem(
                        chunk_index=sc.chunk_index,
                        content=sc.content,
                        char_count=len(sc.content),
                        start_pos=sc.start_pos,
                        end_pos=sc.end_pos,
                    )
                    for sc_id in (s.sub_chunk_ids or [])
                    for sc in [sc_map.get(str(sc_id))]
                    if sc is not None
                ],
            )
            for s in sections
        ],
    )