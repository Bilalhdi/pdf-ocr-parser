import os
# Allow duplicate OpenMP runtimes when using EasyOCR + numpy
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

from flask import Flask, request, jsonify, abort, Response
import pdfplumber
import easyocr
import numpy as np
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Hardcoded API keys (replace with your real values)
FLASK_API_KEY  = "123456789"
GEMINI_API_KEY = "AIzaSyCX-6w1_jLBO4mTBqnKYBaLwFZy587dLDo"
CHUNK_SIZE      = 20_000
OVERLAP         = 2_000
MAX_WORKERS     = 2

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize EasyOCR reader (English only; set gpu=True if you have CUDA)
reader = easyocr.Reader(["en"], gpu=False)

app = Flask(__name__)
parsed_output = None  # holds the last parsed output

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
        "with all values set to null, so I can use it as a mold:\n\n" + fragment
    )
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 1024}
    )
    return model.generate_content(prompt).text.strip()


def gemini_raw(chunk: str, schema: str) -> str:
    prompt = (
        f"Use this JSON schema (keys only, all values=null):\n{schema}\n\n"
        "Now parse ONLY this invoice fragment into that schema (fill in the values):\n\n" + chunk
    )
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 8192}
    )
    return model.generate_content(prompt).text.strip()


def extract_footer(fragment: str) -> str:
    prompt = (
        "This is the *footer* of an invoice. Extract *all* summary fields "
        "(grand total, net balance, etc.) as flat JSON:\n\n" + fragment
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
            pil = page.to_image(resolution=300).original
            arr = np.array(pil)
            texts = reader.readtext(arr, detail=0)
            pages.append("\n".join(texts))
    return "\n".join(pages)

@app.route("/parse", methods=["GET", "POST"])
@require_api_key
def parse_pdf():
    global parsed_output

    if request.method == "GET":
        if not parsed_output:
            abort(404, "No parsed output available yet")
        return Response(parsed_output, mimetype="text/plain")

    if "file" not in request.files:
        abort(400, "No file part")
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        abort(400, "Invalid PDF file")

    raw_text = ocr_pdf(file.stream)
    chunks   = list(chunk_with_overlap(raw_text, CHUNK_SIZE, OVERLAP))
    if not chunks:
        abort(500, "Failed to extract any text")
    schema   = extract_schema(chunks[0])

    outputs = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(gemini_raw, chunks[i], schema): i for i in range(len(chunks))}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                outputs[idx] = fut.result()
            except:
                outputs[idx] = ""

    footer   = extract_footer(chunks[-1])
    combined = "\n\n".join(outputs) + "\n\n// —— Footer summary ——\n" + footer
    parsed_output = combined

    return jsonify({"parsed": combined})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
