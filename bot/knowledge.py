"""
Knowledge base search via pgvector (ERP postgres).
Uses fastembed (ONNX) — same model as embed_index.py, no torch needed on server.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 3
MIN_SCORE = 0.35  # cosine similarity threshold

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=MODEL_NAME)
        logger.info("Knowledge embedder loaded: %s", MODEL_NAME)
    return _embedder


def _embed_sync(text: str) -> list[float]:
    embedder = _get_embedder()
    vectors = list(embedder.embed([text]))
    return vectors[0].tolist()


def _search_sync(query: str) -> list[dict]:
    from bot.erp_db import _connect
    vec = _embed_sync(query)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT source, content,
                   1 - (embedding <=> %s::vector) AS score
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vec, vec, TOP_K),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"source": r[0], "content": r[1], "score": float(r[2])}
        for r in rows
        if float(r[2]) >= MIN_SCORE
    ]


async def search_knowledge(query: str) -> list[dict]:
    """Return top-K relevant knowledge chunks for a query."""
    try:
        return await asyncio.to_thread(_search_sync, query)
    except Exception:
        logger.exception("Knowledge search failed")
        return []


def format_context(chunks: list[dict]) -> str:
    """Format chunks for injection into LLM prompt."""
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        parts.append(f"[{c['source']}]\n{c['content']}")
    return "\n\n---\n\n".join(parts)
