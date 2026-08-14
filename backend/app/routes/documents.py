"""
Document routes — M1 Rewrite: 5-stage pipeline.  M3: 文件夹关联 + 实体高亮。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.atomic_splitter import split_atomic_units
from app.core.embeddings import embed_text
from app.core.entity_highlighter import highlight_entities
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
    DocumentHighlightResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentUpdate,
    HighlightItem,
    SectionBlockItem,
    SubChunkItem,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        total_characters=len(doc.raw_text or ""),
        total_atomic_units=doc.total_atomic_units or 0,
        total_sub_chunks=doc.total_sub_chunks or 0,
        total_section_blocks=doc.total_section_blocks or 0,
        created_at=doc.created_at,
        folder_id=doc.folder_id,
        position=doc.position or 0,
        user_title=doc.user_title,
    )


# ── POST /api/documents ───────────────────────────────────────────────────


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def upload_document(payload: DocumentCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw_text = payload.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text cannot be empty")

    doc_id = uuid.uuid4()
    title = payload.title or raw_text[:60]

    # M3.1: 标题重名检测（仅当用户明确提供标题时）
    if payload.title:
        existing = db.query(Document).filter(Document.title == title).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "conflict",
                    "existing_document_id": str(existing.id),
                    "suggested_title": f"{title} (2)",
                    "message": f"文档「{title}」已存在",
                },
            )

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

        # M3.2: 自动创建实体提取任务（导入资料后自动进入任务列表）
        from app.core.task_manager import task_manager as tm

        ext_task = tm.create_and_schedule(
            db,
            task_type="entity_extraction",
            params={"document_id": str(doc_id), "title": title},
            background_tasks=background_tasks,
        )
        db.commit()

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


# ── PUT /api/documents/{id}（M3: 重命名/移动/排序） ──────────────────────


@router.put("/{id}", response_model=DocumentResponse)
def update_document(id: uuid.UUID, payload: DocumentUpdate, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if payload.title is not None:
        doc.title = payload.title.strip()
    # 用 exclude_unset 检测 folder_id 是否被显式传入（允许设为 None）
    raw = payload.model_dump(exclude_unset=True)
    if "folder_id" in raw:
        doc.folder_id = raw["folder_id"]
    if payload.position is not None:
        doc.position = payload.position
    if payload.user_title is not None:
        doc.user_title = payload.user_title.strip()
    db.commit()
    db.refresh(doc)
    return _doc_to_response(doc)


# ── DELETE /api/documents/{id}（M3） ──────────────────────────────────────


@router.delete("/{id}", status_code=204)
def delete_document(id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()


# ── GET /api/documents/{id}/default（M3: 原文 + 实体高亮） ─────────────


@router.get("/{id}/default", response_model=DocumentHighlightResponse)
def get_document_with_highlights(id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = doc.cleaned_text or doc.raw_text
    highlights = highlight_entities(db, id, content)

    return DocumentHighlightResponse(
        document_id=doc.id,
        title=doc.title,
        content=content,
        highlights=[HighlightItem(**h) for h in highlights],
    )