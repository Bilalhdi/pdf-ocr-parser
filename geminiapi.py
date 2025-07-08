import os
import google.generativeai as genai

API_KEY         = "AIzaSyCX-6w1_jLBO4mTBqnKYBaLwFZy587dLDo"
MODEL_NAME      = "gemini-2.0-flash"
INPUT_TEXT_FILE = r"C:\Users\bilal\OneDrive\Desktop\Agile\ocr stuff\texts\pharmalink_pages1-4.txt"
OUTPUT_DIR      = "output"
OUTPUT_TXT_FILE = "Pharma_World_serial.txt"
CHUNK_SIZE      = 5000
OVERLAP         = 200

genai.configure(api_key=API_KEY)

def chunk_with_overlap(text: str, size: int, overlap: int):
    i = 0
    while i < len(text):
        yield text[i : i+size]
        i += size - overlap

def gemini_raw(chunk: str, pattern: str = "") -> str:
    """
    Send chunk plus an optional pattern hint (the first chunk's output).
    """
    prompt_parts = []
    if pattern:
        prompt_parts.append("Use this exact JSON schema as your pattern:\n" + pattern)
    prompt_parts.append(chunk)
    prompt = (
        "You are an invoice data extractor. Return **only** a JSON-style dictionary as raw text—no explanation.\n\n"
        + "\n\n".join(prompt_parts)
    )

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 4096,
        },
    )
    resp = model.generate_content(prompt)
    return resp.text.strip()

def main():
    # load full OCR-extracted text
    if not os.path.exists(INPUT_TEXT_FILE):
        raise FileNotFoundError(f"Missing input file: {INPUT_TEXT_FILE}")
    full_text = open(INPUT_TEXT_FILE, "r", encoding="utf-8").read()

    chunks = list(chunk_with_overlap(full_text, CHUNK_SIZE, OVERLAP))
    print(f"▶️  Will extract in {len(chunks)} chunks…")

    outputs = []
    pattern = None

    for idx, chunk in enumerate(chunks, start=1):
        print(f" • chunk {idx}/{len(chunks)}…", end="", flush=True)
        try:
            if idx == 1:
                # first chunk: extract normally, capture its output as "pattern"
                raw = gemini_raw(chunk)
                pattern = raw
            else:
                # later chunks: extract, but include the first chunk's output as pattern
                raw = gemini_raw(chunk, pattern=pattern)
            outputs.append(raw)
            print("✅")
        except Exception as e:
            print("⚠️ failed:", e)

    # join each JSON-style block with spacing
    result = "\n\n".join(outputs)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_TXT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"\n✅  Saved raw “JSON-style” output to {out_path}")
    print("\n" + result[:500] + ("…" if len(result) > 500 else ""))

if __name__ == "__main__":
    main()
