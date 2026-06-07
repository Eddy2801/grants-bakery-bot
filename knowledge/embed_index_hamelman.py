"""
Index Hamelman book chunks into knowledge_chunks using OpenAI text-embedding-3-small.

Prerequisites:
  1. SSH tunnel to ERP postgres (if running locally):
       ssh -L 5432:localhost:5432 -i ~/.ssh/id_ed25519_openssh 192.145.37.110
  2. pip install openai psycopg2-binary python-dotenv
  3. .env with OPENAI_API_KEY, ERP_DB_* vars  (or set env vars directly)

Usage:
  python knowledge/embed_index_hamelman.py [--clear] [--dry-run]
  python knowledge/embed_index_hamelman.py --images-only   # only upload images to DB

Schema expected (run migrations/002_knowledge_v2.sql first):
  knowledge_chunks(id, source, chunk_index, content, section, book, has_images, embedding)
  knowledge_images(id, filename, book, data)
  knowledge_chunk_images(chunk_id, image_id)
"""
import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
CHUNKS_JSON   = Path("C:/Users/edgar/Embeddings/hamelman_chunks.json")
IMAGES_DIR    = Path("C:/Users/edgar/Embeddings/images")
SOURCE        = "hamelman"
BOOK_TITLE    = "Bread: A Baker's Book of Techniques and Recipes (Hamelman, 3rd ed.)"
EMBED_MODEL   = "text-embedding-3-small"
EMBED_DIMS    = 1536
BATCH_SIZE    = 100        # OpenAI allows up to 2048 items per call
RATE_LIMIT_RPM = 3000      # text-embedding-3-small tier-1 limit

# Sections to skip (front matter, copyright, legal)
SKIP_SECTIONS = {
    "",               # empty section = front matter
    "RECIPES",        # pure TOC list
}
SKIP_CHUNK_IDS = set(range(0, 7))  # chunks 0-6: cover, copyright, ISBN, TOC

IMAGE_REF_RE = re.compile(r'!\[\]\((_page_\d+_\w+_\d+\.\w+)\)')


def get_db_conn():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    return psycopg2.connect(
        host=os.getenv("ERP_DB_HOST", "localhost"),
        port=int(os.getenv("ERP_DB_PORT", 5432)),
        dbname=os.getenv("ERP_DB_NAME", "gbakery"),
        user=os.getenv("ERP_DB_USER", "postgres"),
        password=os.getenv("ERP_DB_PASS", ""),
    )


def load_chunks() -> list[dict]:
    path = Path("C:/Users/edgar/Embeddings/hamelman_chunks.json")
    logger.info("Loading %s", path)
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def filter_chunks(chunks: list[dict]) -> list[dict]:
    """Remove front matter and pure index/TOC chunks."""
    kept = []
    for c in chunks:
        if c["chunk_id"] in SKIP_CHUNK_IDS:
            continue
        section = c["metadata"].get("Section", "")
        if section in SKIP_SECTIONS:
            continue
        # Skip index pages (html span artifacts)
        if section.startswith("<span") or section.startswith("INDEX"):
            continue
        kept.append(c)
    logger.info("Filtered: %d → %d chunks", len(chunks), len(kept))
    return kept


def extract_image_refs(text: str) -> tuple[str, list[str]]:
    """Return (clean_text, [image_filenames])."""
    refs = IMAGE_REF_RE.findall(text)
    clean = IMAGE_REF_RE.sub("", text).strip()
    return clean, refs


def embed_batch(texts: list[str], client) -> list[list[float]]:
    """Embed a batch of texts, return list of vectors."""
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
        dimensions=EMBED_DIMS,
    )
    # Sort by index to ensure order
    items = sorted(resp.data, key=lambda x: x.index)
    return [item.embedding for item in items]


def index_images(cur, images_dir: Path):
    """Load all JPEG/PNG files into knowledge_images table."""
    files = sorted(images_dir.glob("*.jpeg")) + sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    logger.info("Uploading %d images to knowledge_images...", len(files))
    inserted = 0
    for f in files:
        data = f.read_bytes()
        cur.execute(
            """
            INSERT INTO knowledge_images (filename, book, data)
            VALUES (%s, %s, %s)
            ON CONFLICT (filename) DO NOTHING
            """,
            (f.name, SOURCE, psycopg2.Binary(data)),
        )
        inserted += cur.rowcount
    logger.info("Inserted %d new images (%d already existed)", inserted, len(files) - inserted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear",       action="store_true", help="Delete existing hamelman chunks before indexing")
    parser.add_argument("--dry-run",     action="store_true", help="Embed but do not insert into DB")
    parser.add_argument("--images-only", action="store_true", help="Only upload images, skip text indexing")
    args = parser.parse_args()

    import openai
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=api_key)

    conn = get_db_conn()
    cur = conn.cursor()

    # ── Images ──────────────────────────────────────────────────────────────────
    images_dir = Path("C:/Users/edgar/Embeddings/images")
    if images_dir.exists():
        index_images(cur, images_dir)
        conn.commit()
    else:
        logger.warning("Images dir not found: %s", images_dir)

    if args.images_only:
        cur.close()
        conn.close()
        return

    # ── Text chunks ─────────────────────────────────────────────────────────────
    raw_chunks = load_chunks()
    chunks = filter_chunks(raw_chunks)

    if args.clear:
        cur.execute("DELETE FROM knowledge_chunks WHERE source = %s", (SOURCE,))
        logger.info("Cleared existing chunks for source=%s", SOURCE)
        conn.commit()

    # Check which chunk_indexes already exist
    cur.execute("SELECT chunk_index FROM knowledge_chunks WHERE source = %s", (SOURCE,))
    existing = {r[0] for r in cur.fetchall()}
    chunks = [c for c in chunks if c["chunk_id"] not in existing]
    logger.info("%d chunks to embed (skipping %d already indexed)", len(chunks), len(raw_chunks) - len(chunks))

    if not chunks:
        logger.info("Nothing to do.")
        cur.close()
        conn.close()
        return

    # ── Batch embed ──────────────────────────────────────────────────────────────
    total = len(chunks)
    processed = 0
    errors = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start: batch_start + BATCH_SIZE]

        # Extract clean text and image refs
        texts = []
        image_ref_map = {}  # index_in_batch → [filenames]
        for i, c in enumerate(batch):
            clean_text, refs = extract_image_refs(c["text"])
            texts.append(clean_text)
            if refs:
                image_ref_map[i] = refs

        logger.info("Embedding batch %d-%d / %d...",
                    batch_start + 1, batch_start + len(batch), total)

        if args.dry_run:
            logger.info("  [dry-run] would embed %d texts", len(texts))
            processed += len(batch)
            continue

        try:
            vectors = embed_batch(texts, client)
        except Exception as e:
            logger.error("Embedding failed for batch %d-%d: %s", batch_start, batch_start + len(batch), e)
            errors += len(batch)
            time.sleep(5)
            continue

        # Insert chunks
        for i, (c, vec, text) in enumerate(zip(batch, vectors, texts)):
            meta = c.get("metadata", {})
            section = (
                meta.get("Sub_Section")
                or meta.get("Recipe_or_Chapter")
                or meta.get("Section")
                or None
            )
            has_images = bool(image_ref_map.get(i))

            cur.execute(
                """
                INSERT INTO knowledge_chunks
                    (source, chunk_index, content, section, book, has_images, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (source, chunk_index) DO NOTHING
                RETURNING id
                """,
                (SOURCE, c["chunk_id"], text, section, BOOK_TITLE, has_images,
                 vec),
            )
            row = cur.fetchone()
            if not row:
                continue  # already existed
            chunk_db_id = row[0]

            # Link images
            for filename in image_ref_map.get(i, []):
                cur.execute(
                    "SELECT id FROM knowledge_images WHERE filename = %s", (filename,)
                )
                img_row = cur.fetchone()
                if img_row:
                    cur.execute(
                        """
                        INSERT INTO knowledge_chunk_images (chunk_id, image_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """,
                        (chunk_db_id, img_row[0]),
                    )

        conn.commit()
        processed += len(batch)
        logger.info("  Committed. Progress: %d/%d", processed, total)

        # Gentle rate limiting (3000 RPM = 50/s, batches are large so rarely needed)
        time.sleep(0.1)

    logger.info("Done. %d indexed, %d errors.", processed - errors, errors)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
