import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://learn:learn123@postgres:5432/learn",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Drop old temp tables, verify embedding dim, create all tables + indexes."""
    from app.core.embeddings import verify_embedding_dim

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Clean-slate: drop old tables that conflict with new schema
        conn.execute(text("DROP TABLE IF EXISTS paragraph_blocks CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS sub_chunks CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS section_blocks CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
        conn.commit()

    # Verify embedding dimension matches configured value
    verify_embedding_dim()

    # Ensure questions table has options column (M2.8.2)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS options JSONB"))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    # M2: pgvector IVFFlat index for sub_chunk vector search
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sub_chunks_embedding "
            "ON sub_chunks USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        ))
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
