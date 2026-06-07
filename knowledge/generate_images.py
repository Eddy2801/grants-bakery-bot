"""
Two-pass image pipeline for Hamelman book illustrations:
  Pass 1: GPT-4o Vision → classify each image + write functional description
  Pass 2: For technique_step / diagram → generate branded illustration via fal.ai Flux

Usage:
  pip install openai fal-client psycopg2-binary python-dotenv

  # Classify all images (no generation):
  python knowledge/generate_images.py --classify-only

  # Full pipeline (classify + generate):
  python knowledge/generate_images.py --model dev     # or --model schnell

  # Re-generate already classified images (skip Vision pass):
  python knowledge/generate_images.py --generate-only --model dev

  # Test on first 5 images:
  python knowledge/generate_images.py --limit 5 --model schnell

DB connection: reads ERP_DB_* and OPENAI_API_KEY / FAL_KEY from .env or env vars.
Requires SSH tunnel if running locally:
  ssh -L 5432:localhost:5432 -i ~/.ssh/id_ed25519_openssh 192.145.37.110
"""
import argparse
import base64
import logging
import os
import sys
import time
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Types to generate illustrations for ───────────────────────────────────────
GENERATE_TYPES = {"technique_step", "diagram"}

# ── Brand style prompt (injected into every generation) ───────────────────────
BRAND_STYLE = (
    "Minimalist artisan bakery technical illustration. "
    "Warm cream background (#F4EDE4), dark brown lines and shapes (#3A3129), "
    "medium taupe accents (#8D847C). "
    "Clean elegant line art, no text, no watermarks, no human faces, no logos. "
    "Original artistic interpretation only. "
    "Never reproduce any copyrighted material or identifiable book illustrations."
)

VISION_SYSTEM = """You are analyzing images from a professional bread baking book.
For each image:
1. Classify it as exactly one of:
   - technique_step  (showing a hands-on baking technique: shaping, folding, scoring, mixing, etc.)
   - bread_photo     (showing a finished bread product)
   - diagram         (chart, table, formula, schematic with measurements)
   - decoration      (decorative bread art, display piece)
   - other           (portraits, maps, text-only, equipment without context)

2. Write a concise functional description (1-2 sentences) of WHAT is shown —
   the baking subject or technique — NOT the artistic style.
   Never quote book text verbatim. Rephrase in your own words.

Reply in exactly this format (no extra text):
TYPE: <type>
DESCRIPTION: <description>"""


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


def classify_image(client, image_bytes: bytes) -> tuple[str, str]:
    """Call GPT-4o Vision. Returns (image_type, description)."""
    b64 = base64.b64encode(image_bytes).decode()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
                    }
                ],
            },
        ],
        max_tokens=150,
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    image_type = "other"
    description = text
    for line in text.splitlines():
        if line.startswith("TYPE:"):
            image_type = line.split(":", 1)[1].strip().lower()
        elif line.startswith("DESCRIPTION:"):
            description = line.split(":", 1)[1].strip()
    return image_type, description


def get_chunk_context(cur, image_id: int) -> str:
    """Fetch linked chunk texts for an image. Returns combined context string."""
    cur.execute(
        """SELECT c.section, c.content
           FROM knowledge_chunks c
           JOIN knowledge_chunk_images ci ON ci.chunk_id = c.id
           WHERE ci.image_id = %s
           ORDER BY c.chunk_index""",
        (image_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return ""
    parts = []
    for section, content in rows:
        header = f"[{section}] " if section else ""
        parts.append(header + content[:500])
    return "\n\n".join(parts)


def build_illustration_concept(oai_client, chunk_context: str, image_description: str) -> str:
    """Use GPT-4o to synthesize a specific illustration concept from chunk text."""
    system = (
        "You are a technical illustration director for an artisan bakery brand. "
        "Given a passage from a bread baking book and a rough description of a related image, "
        "write a precise, concrete illustration brief (2-3 sentences) describing EXACTLY what "
        "should be shown in a technical illustration. Focus on the specific technique, objects, "
        "and action. No artistic style. No people's faces. No text in illustration."
    )
    user = (
        f"Book passage:\n{chunk_context[:800]}\n\n"
        f"Related image description: {image_description}\n\n"
        "Write the illustration brief:"
    )
    resp = oai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=120,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def generate_illustration(fal_client, concept: str, model: str) -> bytes:
    """Call fal.ai Flux. Returns raw PNG/JPEG bytes."""
    model_id = f"fal-ai/flux/{model}"
    prompt = f"{BRAND_STYLE} {concept}"

    result = fal_client.subscribe(
        model_id,
        arguments={
            "prompt": prompt,
            "image_size": "square_hd",       # 1024×1024
            "num_inference_steps": 28 if model == "dev" else 4,
            "num_images": 1,
            "enable_safety_checker": True,
        },
    )
    image_url = result["images"][0]["url"]

    import urllib.request
    with urllib.request.urlopen(image_url) as r:
        return r.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--classify-only",  action="store_true", help="Only run Vision classification, no generation")
    parser.add_argument("--generate-only",  action="store_true", help="Skip Vision, only generate for already-classified images")
    parser.add_argument("--model",          default="schnell", choices=["schnell", "dev"], help="Flux model (default: schnell)")
    parser.add_argument("--limit",          type=int, default=0, help="Process at most N images (for testing)")
    parser.add_argument("--reclassify",     action="store_true", help="Re-classify images that already have a type")
    parser.add_argument("--regen-ids",      type=str, default="", help="Comma-separated image IDs to forcibly regenerate")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    openai_key = os.getenv("OPENAI_API_KEY")
    fal_key    = os.getenv("FAL_KEY")

    if not args.generate_only and not openai_key:
        sys.exit("OPENAI_API_KEY not set")
    if not args.classify_only and not fal_key:
        sys.exit("FAL_KEY not set")

    import openai
    import fal_client

    os.environ["FAL_KEY"] = fal_key or ""
    oai = openai.OpenAI(api_key=openai_key) if openai_key else None

    conn = get_db_conn()
    cur = conn.cursor()

    # ── Load images to process ─────────────────────────────────────────────────
    regen_ids = [int(x) for x in args.regen_ids.split(",") if x.strip()]

    if regen_ids:
        cur.execute(
            "SELECT id, filename, data, image_type, description FROM knowledge_images WHERE id = ANY(%s) ORDER BY id",
            (regen_ids,),
        )
    elif args.generate_only:
        cur.execute(
            """SELECT id, filename, data, image_type, description
               FROM knowledge_images
               WHERE image_type = ANY(%s) AND generated_data IS NULL
               ORDER BY id""",
            (list(GENERATE_TYPES),),
        )
    elif args.reclassify:
        cur.execute("SELECT id, filename, data, image_type, description FROM knowledge_images ORDER BY id")
    else:
        cur.execute(
            """SELECT id, filename, data, image_type, description
               FROM knowledge_images
               WHERE image_type IS NULL
               ORDER BY id"""
        )

    rows = cur.fetchall()
    if args.limit:
        rows = rows[: args.limit]

    logger.info("Images to process: %d", len(rows))
    if not rows:
        logger.info("Nothing to do.")
        cur.close()
        conn.close()
        return

    # ── Stats ──────────────────────────────────────────────────────────────────
    classified = 0
    generated  = 0
    errors     = 0

    for img_id, filename, img_data, existing_type, existing_desc in rows:
        logger.info("Processing [%d] %s", img_id, filename)

        # ── Pass 1: Vision classification ──────────────────────────────────────
        image_type  = existing_type
        description = existing_desc

        if not args.generate_only and (image_type is None or args.reclassify):
            if img_data is None:
                logger.warning("  No image data, skipping classification")
                continue
            try:
                image_type, description = classify_image(oai, bytes(img_data))
                cur.execute(
                    "UPDATE knowledge_images SET image_type=%s, description=%s WHERE id=%s",
                    (image_type, description, img_id),
                )
                conn.commit()
                classified += 1
                logger.info("  → %s: %s", image_type, description[:80])
            except Exception as e:
                logger.error("  Vision error: %s", e)
                errors += 1
                time.sleep(2)
                continue

        if args.classify_only:
            continue

        # ── Pass 2: Generate illustration ──────────────────────────────────────
        if image_type not in GENERATE_TYPES:
            logger.info("  Skipping generation (type=%s)", image_type)
            continue

        if not description:
            logger.warning("  No description, skipping generation")
            continue

        try:
            # Build concept from chunk context (if linked chunks exist)
            chunk_context = get_chunk_context(cur, img_id)
            if chunk_context and oai:
                concept = build_illustration_concept(oai, chunk_context, description)
                logger.info("  Concept: %s", concept[:120])
            else:
                concept = description
                logger.info("  No chunk context, using description")

            img_bytes = generate_illustration(fal_client, concept, args.model)
            cur.execute(
                "UPDATE knowledge_images SET generated_data=%s WHERE id=%s",
                (psycopg2.Binary(img_bytes), img_id),
            )
            conn.commit()
            generated += 1
            logger.info("  Generated %d bytes", len(img_bytes))
        except Exception as e:
            logger.error("  Generation error: %s", e)
            errors += 1
            time.sleep(3)

        time.sleep(0.2)  # gentle rate limit

    logger.info(
        "Done. Classified: %d, Generated: %d, Errors: %d",
        classified, generated, errors,
    )

    # Print type breakdown
    cur.execute(
        "SELECT image_type, COUNT(*) FROM knowledge_images GROUP BY image_type ORDER BY 2 DESC"
    )
    logger.info("Type breakdown:")
    for row in cur.fetchall():
        logger.info("  %-20s %d", row[0] or "NULL", row[1])

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
