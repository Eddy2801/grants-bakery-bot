"""
Knowledge base search via pgvector (ERP postgres).
Uses OpenAI text-embedding-3-small (1536 dims) for cross-lingual retrieval.
EN source content is retrieved correctly for LV/RU/EN queries without translation.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

TOP_K = 4
MIN_SCORE = 0.30  # cosine similarity threshold (lower: cross-lingual gap)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536


def _embed_sync(text: str) -> list[float]:
    import openai
    from bot.config import config
    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.embeddings.create(model=EMBED_MODEL, input=text, dimensions=EMBED_DIMS)
    return resp.data[0].embedding


def _search_sync(query: str) -> list[dict]:
    from bot.erp_db import _connect
    vec = _embed_sync(query)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.id, c.source, c.book, c.section, c.content, c.has_images,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM knowledge_chunks c
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec, vec, TOP_K),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        score = float(r[6])
        if score < MIN_SCORE:
            continue
        results.append({
            "id": r[0],
            "source": r[1],
            "book": r[2],
            "section": r[3],
            "content": r[4],
            "has_images": r[5],
            "score": score,
        })
    return results


async def search_knowledge(query: str) -> list[dict]:
    """Return top-K relevant knowledge chunks for a query."""
    try:
        return await asyncio.to_thread(_search_sync, query)
    except Exception:
        logger.exception("Knowledge search failed")
        return []


def format_context(chunks: list[dict]) -> str:
    """Format chunks for injection into LLM system prompt."""
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        header = c["source"]
        if c.get("section"):
            header += f" / {c['section']}"
        parts.append(f"[{header}]
{c['content']}")
    return "

---

".join(parts)
