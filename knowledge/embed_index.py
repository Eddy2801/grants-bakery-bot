"""
Local GPU indexing script — runs on Windows with RTX 3060.

Usage:
  1. Open SSH tunnel in a separate terminal:
       ssh -L 5432:localhost:5432 -i ~/.ssh/id_ed25519_openssh 192.145.37.110
  2. Install deps (once):
       pip install sentence-transformers psycopg2-binary torch torchvision --index-url https://download.pytorch.org/whl/cu121
  3. Run:
       python knowledge/embed_index.py [--clear] [file1.md file2.md ...]
       # without args — indexes all .md files in knowledge/
"""
import argparse
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import torch
from sentence_transformers import SentenceTransformer

# ── Config ─────────────────────────────────────────────────────
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 400       # target tokens per chunk (≈words * 1.3)
CHUNK_OVERLAP = 50     # overlap between chunks in words

DB_DSN = "postgresql://postgres:SNmF0Sj$@localhost:5432/gbakery"
KNOWLEDGE_DIR = Path(__file__).parent


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {MODEL_NAME} on {device} ({torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    return model


def chunk_text(text: str, chunk_words: int = 300, overlap_words: int = 50) -> list[str]:
    """Split text into overlapping chunks by paragraph, then by word count."""
    # Split on double newline (paragraph boundary)
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    chunks = []
    current_words = []

    for para in paragraphs:
        words = para.split()
        if len(current_words) + len(words) > chunk_words and current_words:
            chunks.append(" ".join(current_words))
            # keep overlap
            current_words = current_words[-overlap_words:] + words
        else:
            current_words.extend(words)

        # force-flush if single paragraph is too long
        while len(current_words) > chunk_words * 1.5:
            chunks.append(" ".join(current_words[:chunk_words]))
            current_words = current_words[chunk_words - overlap_words:]

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def index_file(cur, model, md_path: Path, clear_source: bool = False):
    source = md_path.stem  # filename without extension
    text = md_path.read_text(encoding="utf-8")

    # Strip markdown headings markers for cleaner embeddings (keep text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    chunks = chunk_text(text)
    print(f"  {md_path.name}: {len(chunks)} chunks")

    if clear_source:
        cur.execute("DELETE FROM knowledge_chunks WHERE source = %s", (source,))

    texts = chunks
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=len(texts) > 5,
        normalize_embeddings=True,
    )

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        cur.execute(
            """
            INSERT INTO knowledge_chunks (source, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s::vector)
            ON CONFLICT DO NOTHING
            """,
            (source, i, chunk, emb.tolist()),
        )

    return len(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help=".md files to index (default: all in knowledge/)")
    parser.add_argument("--clear", action="store_true", help="delete existing chunks for each source before re-indexing")
    args = parser.parse_args()

    if args.files:
        md_files = [Path(f) for f in args.files]
    else:
        md_files = [f for f in KNOWLEDGE_DIR.glob("*.md")]

    if not md_files:
        print("No .md files found.")
        sys.exit(0)

    model = load_model()

    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    total = 0
    for f in sorted(md_files):
        print(f"\nIndexing {f.name}...")
        n = index_file(cur, model, f, clear_source=args.clear)
        total += n

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. {total} chunks indexed into knowledge_chunks.")


if __name__ == "__main__":
    main()
