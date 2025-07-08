import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai
from dotenv import load_dotenv    # ← new


# ── CONFIG ────────────────────────────────────────────────────────────────────
load_dotenv()                      # read .env into os.environ
API_KEY = os.getenv("API_KEY")   # load from .env
MODEL_NAME      = "gemini-2.0-flash"
INPUT_TEXT_FILE = r"C:\Users\bilal\OneDrive\Desktop\Agile\ocr stuff\scripts\output\Pharma_link1-4.txt"
OUTPUT_DIR      = "output"
OUTPUT_TXT_FILE = "Texas[1].txt"

# Increase chunk size now that we can generate up to 8k tokens of output.
# Rough rule‐of‐thumb: ~4 chars/token, so 20 000 chars ≈ 5 000 tokens of input,
# leaving room for ~3 000 tokens of output.
CHUNK_SIZE      = 20_000
OVERLAP         = 2_000
MAX_WORKERS     = 2

genai.configure(api_key=API_KEY)

# ── HELPERS ────────────────────────────────────────────────────────────────────
def chunk_with_overlap(text: str, size: int, overlap: int):
    """Yield overlapping slices of `text` each ~`size` chars long."""
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size - overlap

def extract_schema(fragment: str) -> str:
    """Generate a null-valued JSON keys template from the first chunk."""
    prompt = (
        "Here is one invoice fragment.  Return ONLY the JSON *keys* (in order),\n"
        "with all values set to null, so I can use it as a mold:\n\n"
        + fragment
    )
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 1024
        }
    )
    return model.generate_content(prompt).text.strip()

def gemini_raw(chunk: str, schema: str) -> str:
    """Fill the schema with values extracted from this chunk."""
    prompt = (
        "Use this JSON schema (keys only, all values=null) for your output:\n"
        + schema
        + "\n\n ignore any \\n parsed through in between any words that dont make sense like Se\\np Now parse ONLY this invoice fragment into that schema (fill in the values):\n\n"
        + chunk 
    )
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 8192
        }
    )
    return model.generate_content(prompt).text.strip()

def extract_footer(fragment: str) -> str:
    """
    Free-form extraction of footer fields:
     - Grand Total
     - Net/Closing Balance
     - Any ageing buckets or summary tables
    """
    prompt = (
        "This is the *footer* of an invoice or statement.  Extract *all* summary fields\n"
        "(grand total, net balance, ageing buckets, totals by month, etc.) as a flat JSON\n"
        "object.  Output *only* that JSON.\n\n"
        + fragment
    )
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 2048
        }
    )
    return model.generate_content(prompt).text.strip()

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    # 1) Read your full extracted-text file
    if not os.path.exists(INPUT_TEXT_FILE):
        raise FileNotFoundError(f"{INPUT_TEXT_FILE} not found")
    full_text = open(INPUT_TEXT_FILE, "r", encoding="utf-8").read()

    # 2) Break into overlapping chunks
    chunks = list(chunk_with_overlap(full_text, CHUNK_SIZE, OVERLAP))
    n = len(chunks)
    print(f"▶️  {n} chunks → extracting schema from chunk 1…")

    # 3) Get a schema template from the first chunk
    schema = extract_schema(chunks[0])
    print("Schema template:\n", schema, "\n")

    # 4) Fill *all* chunks in parallel
    outputs = [None] * n
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {
            exe.submit(gemini_raw, chunks[i], schema): i
            for i in range(n)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                out = fut.result()
                print(f" • chunk {idx+1}/{n} → ✅")
                outputs[idx] = out
            except Exception as e:
                print(f" • chunk {idx+1}/{n} → ⚠️ {e}")
                outputs[idx] = ""

    # 5) Extract footer from the very last chunk
    print(f"\n▶️  Extracting footer from chunk {n}…")
    footer_json = extract_footer(chunks[-1])
    print(" • footer →", footer_json[:200].replace("\n", " ") + ("…" if len(footer_json)>200 else ""))

    # 6) Stitch together all chunk-outputs + footer
    combined = "\n\n".join(outputs) \
             + "\n\n" \
             + "// —— Footer summary ——\n" \
             + footer_json

    # 7) Save as a “.txt” that merely *looks* like JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_TXT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(combined)

    print(f"\n✅  Saved “JSON-style” result (with footer) to {out_path}")

if __name__ == "__main__":
    main()

