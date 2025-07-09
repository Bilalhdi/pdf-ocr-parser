import os
from flask import Flask, request, jsonify, abort, Response
import pdfplumber
import pytesseract
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ────────────────────────────────────────────────────────────────────
dotenv_path = find_dotenv()
if not dotenv_path:
    raise RuntimeError("❌ Couldn't find a .env file anywhere in this tree")
load_dotenv(dotenv_path)

FLASK_API_KEY   = os.getenv("FLASK_API_KEY")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
TESSERACT_CMD   = os.getenv("TESSERACT_CMD")
CHUNK_SIZE      = 20_000
OVERLAP         = 2_000
MAX_WORKERS     = 2

if not all([FLASK_API_KEY, GEMINI_API_KEY, TESSERACT_CMD]):
    raise RuntimeError("Please set FLASK_API_KEY, GEMINI_API_KEY, and TESSERACT_CMD in your .env")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

# holds the last parsed output in memory
parsed_output = None

def require_api_key(f):
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-KEY") != FLASK_API_KEY:
            abort(401, "Invalid or missing API key")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def allowed_file(filename):
    return filename.lower().endswith(".pdf")

def chunk_with_overlap(text: str, size: int, overlap: int):
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size - overlap

def extract_schema(fragment: str) -> str:
    prompt = (
        "Here is one invoice fragment. Return ONLY the JSON *keys* (in order),\n"
        "with all values set to null, so I can use it as a mold:\n\n"
        + fragment
    )
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 1024}
    )
    return model.generate_content(prompt).text.strip()

def gemini_raw(chunk: str, schema: str) -> str:
    prompt = (
        "Use this JSON schema (keys only, all values=null) for your output:\n"
        + schema +
        "\n\nIgnore any \\n parsed through in between words that don't make sense like Se\\np. "
        "Now parse ONLY this invoice fragment into that schema (fill in the values):\n\n"
        + chunk
    )
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 8192}
    )
    return model.generate_content(prompt).text.strip()

def extract_footer(fragment: str) -> str:
    prompt = (
        "This is the *footer* of an invoice or statement. Extract *all* summary fields\n"
        "(grand total, net balance, ageing buckets, totals by month, etc.) as a flat JSON\n"
        "object. Output *only* that JSON.\n\n"
        + fragment
    )
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 2048}
    )
    return model.generate_content(prompt).text.strip()

def ocr_pdf(file_stream) -> str:
    pages = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=200).original
            pages.append(pytesseract.image_to_string(img))
    return "\n".join(pages)

@app.route("/parse", methods=["GET", "POST"])
@require_api_key
def parse_pdf():
    global parsed_output

    if request.method == "GET":
        if not parsed_output:
            abort(404, "No parsed output available yet")
        # return the last parsed text as plain text
        return Response(parsed_output, mimetype="text/plain")

    # POST: user uploads a PDF
    if "file" not in request.files:
        abort(400, "No file part")
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        abort(400, "No selected PDF file")

    # 1) OCR
    raw_text = ocr_pdf(file.stream)

    # 2) Chunk + schema
    chunks = list(chunk_with_overlap(raw_text, CHUNK_SIZE, OVERLAP))
    if not chunks:
        abort(500, "Failed to extract any text")
    schema = extract_schema(chunks[0])

    # 3) Fill each chunk in parallel
    outputs = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(gemini_raw, chunks[i], schema): i for i in range(len(chunks))}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                outputs[idx] = fut.result()
            except Exception:
                outputs[idx] = ""

    # 4) Footer
    footer_json = extract_footer(chunks[-1])

    # 5) Combine into one string
    combined = "\n\n".join(outputs) + "\n\n// —— Footer summary ——\n" + footer_json

    # store for later GET
    parsed_output = combined

    # also return it in the POST response
    return jsonify({"parsed": combined})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
