"""
Quick comparison: Flux/schnell vs Flux/dev on 3 sample technique_step images.
Saves side-by-side results to C:/Users/edgar/Embeddings/compare/
"""
import os, sys, time
from pathlib import Path
import urllib.request
import psycopg2

OUT_DIR = Path("C:/Users/edgar/Embeddings/compare")
OUT_DIR.mkdir(exist_ok=True)

BRAND_STYLE = (
    "Minimalist artisan bakery technical illustration. "
    "Warm cream background (#F4EDE4), dark brown lines and shapes (#3A3129), "
    "medium taupe accents (#8D847C). "
    "Clean elegant line art, no text, no watermarks, no human faces, no logos. "
    "Original artistic interpretation only. "
    "Never reproduce any copyrighted material."
)

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

def generate(fal_client, description, model):
    result = fal_client.subscribe(
        f"fal-ai/flux/{model}",
        arguments={
            "prompt": f"{BRAND_STYLE} Subject: {description}",
            "image_size": "square_hd",
            "num_inference_steps": 28 if model == "dev" else 4,
            "num_images": 1,
            "enable_safety_checker": True,
        },
    )
    url = result["images"][0]["url"]
    with urllib.request.urlopen(url) as r:
        return r.read()

def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    fal_key = os.getenv("FAL_KEY")
    if not fal_key:
        sys.exit("FAL_KEY not set")
    os.environ["FAL_KEY"] = fal_key

    import fal_client

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, filename, description FROM knowledge_images
           WHERE image_type = 'technique_step' AND description IS NOT NULL
           ORDER BY id LIMIT 3"""
    )
    samples = cur.fetchall()
    conn.close()

    print(f"Comparing {len(samples)} samples...\n")
    for img_id, filename, description in samples:
        print(f"[{img_id}] {filename}")
        print(f"  Description: {description[:100]}")
        for model in ("schnell", "dev"):
            print(f"  Generating {model}...", end="", flush=True)
            t = time.time()
            data = generate(fal_client, description, model)
            elapsed = time.time() - t
            out_path = OUT_DIR / f"{img_id}_{model}.jpg"
            out_path.write_bytes(data)
            print(f" {elapsed:.1f}s → {out_path.name} ({len(data)//1024}KB)")
        print()

    print(f"Results saved to: {OUT_DIR}")
    print("Open the folder to compare schnell vs dev side by side.")

if __name__ == "__main__":
    main()
