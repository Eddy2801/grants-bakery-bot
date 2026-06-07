-- Migration 002: Rebuild knowledge_chunks for 1536-dim OpenAI embeddings
-- + knowledge_images and chunk↔image association table
-- Run on ERP postgres (gbakery DB)

-- 1. Drop old table (was vector(384))
DROP TABLE IF EXISTS knowledge_chunks CASCADE;

-- 2. Re-create with 1536-dim embeddings and richer metadata
CREATE TABLE knowledge_chunks (
    id            SERIAL PRIMARY KEY,
    source        VARCHAR(200)  NOT NULL,   -- e.g. "hamelman", "delivery_policy"
    chunk_index   INTEGER       NOT NULL,
    content       TEXT          NOT NULL,
    section       VARCHAR(500),             -- chapter / section title
    book          VARCHAR(200),             -- full book title / source label
    has_images    BOOLEAN       NOT NULL DEFAULT FALSE,
    embedding     VECTOR(1536),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (source, chunk_index)
);

CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX ON knowledge_chunks (source);

-- 3. Images catalogue
CREATE TABLE IF NOT EXISTS knowledge_images (
    id               SERIAL PRIMARY KEY,
    filename         VARCHAR(300) UNIQUE NOT NULL,  -- e.g. "_page_148_Picture_0.jpeg"
    book             VARCHAR(200),
    data             BYTEA,
    telegram_file_id VARCHAR(200),                  -- cached after first Telegram upload
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Chunk ↔ image association
CREATE TABLE IF NOT EXISTS knowledge_chunk_images (
    chunk_id   INTEGER NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    image_id   INTEGER NOT NULL REFERENCES knowledge_images(id) ON DELETE CASCADE,
    PRIMARY KEY (chunk_id, image_id)
);
