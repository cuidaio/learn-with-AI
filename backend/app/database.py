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
    """Drop old temp tables, verify embedding dim, create all tables + M3 migrations."""
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

    # M2.8.2: Ensure questions table has options column
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

    # M3: Ensure folders table exists
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS folders (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                parent_id UUID,
                position INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

    # M3: Ensure learning_events table exists
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS learning_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
                event_type VARCHAR(30) NOT NULL,
                entity_id UUID,
                sub_chunk_id UUID,
                question_id UUID,
                context JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

    # M3: Add card columns to tasks
    with engine.connect() as conn:
        for col in ["card_title", "card_icon", "result_content_type"]:
            conn.execute(text(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {col} VARCHAR(255)"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_default INT DEFAULT 0"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS progress INT DEFAULT 0"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS progress_text VARCHAR(255)"))
        conn.commit()

    # M3: Add folder columns to documents
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id UUID"))
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS position INT DEFAULT 0"))
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_title VARCHAR(255)"))
        conn.commit()

    # M3.6: Add entity filter columns
    with engine.connect() as conn:
        for col in ["introduction_context", "filter_reason"]:
            conn.execute(text(f"ALTER TABLE entities ADD COLUMN IF NOT EXISTS {col} TEXT"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS filter_action VARCHAR(20) DEFAULT 'pending'"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS filter_metadata JSONB DEFAULT '{}'::jsonb"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'llm'"))
        conn.commit()

    # M3: Create indexes
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_events_doc ON learning_events(document_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_events_type ON learning_events(event_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)"))
        conn.commit()

    # M3.11: Create app_config table + seed defaults
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                key VARCHAR(100) NOT NULL UNIQUE,
                value JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            INSERT INTO app_config (key, value) VALUES
            ('embedding', '{"base_url": "https://api.siliconflow.cn/v1/", "api_key": "", "model": "Qwen/Qwen3-Embedding-4B"}'),
            ('llm', '{"base_url": "https://api.deepseek.com/v1/", "api_key": "", "model": "deepseek-v4-flash"}')
            ON CONFLICT (key) DO NOTHING
        """))
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
