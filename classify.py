# classify.py

import os
import sys
import json
import re
import subprocess

# —— CONFIGURE Paths & Model ——
SCRIPT_DIR = os.path.dirname(__file__)
RAW_TXT    = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "texts", "AXIA_raw.txt"))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "output"))
MODEL      = "llama3.2:1b"

def parse_money_to_float(s: str):
    """
    Strip commas/currency, preserve the decimal point, convert to float.
    e.g. "7,798.000" → 7798.0
    """
    if not isinstance(s, str): 
        return None
    # remove commas and any non-digit/non-dot characters except the dot
    cleaned = re.sub(r"[^\d.]", "", s)
    # if more than one dot, keep last as decimal separator
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None

def llama_classify(text: str) -> dict:
    prompt = (
        "You are a JSON extractor for financial statements.\n\n"
        f"{text}\n\n"
        "Step 1: Extract these top-level fields (missing → null):\n"
        "  • StatementDate   (from “Customer Statement as on …”)\n"
        "  • AccountCode     (label “New A/C Code”)\n"
        "  • CustomerName    (label “Customer Name”)\n"
        "  • PaymentTerms    (label “Payment Terms”, keep days as integer)\n\n"
        "Step 2: Locate the main table whose header row reads exactly:\n"
        "  Invoice Date | Ship To | Invoice No. | Reference | Debit | Credit | Balance\n"
        "Parse *each* row after that into an object with those keys.\n"
        "  - Convert dates to ISO YYYY-MM-DD\n"
        "  - Convert numbers to floats (strip commas)\n"
        "  - Missing Debit or Credit → null\n\n"
        "Output *only* a single JSON object:\n"
        "{\n"
        "  \"StatementDate\":...,  \n"
        "  \"AccountCode\":...,    \n"
        "  \"CustomerName\":...,   \n"
        "  \"PaymentTerms\":...,   \n"
        "  \"LineItems\": [ { ... }, ... ]\n"
        "}\n"
        "Do not output any extra text or code blocks."
    )

    p = subprocess.Popen(
        ["ollama", "run", MODEL, prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out_b, err_b = p.communicate()
    out = out_b.decode("utf-8", errors="ignore").strip()
    err = err_b.decode("utf-8", errors="ignore").strip()
    if p.returncode != 0:
        print("❌ Ollama failed:\n", err or out)
        sys.exit(1)

    # ensure JSON ends with }
    if not out.endswith("}"):
        out += "}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("\n❌ JSON parse error. Raw output:\n", out)
        sys.exit(1)

def post_process(data: dict) -> dict:
    # 1) Fix PaymentTerms → integer
    pt = data.get("PaymentTerms")
    if isinstance(pt, str) and pt.strip().endswith("DAYS"):
        # e.g. "90 DAYS"
        num = re.search(r"(\d+)", pt)
        data["PaymentTerms"] = int(num.group(1)) if num else None

    # 2) LineItems numeric conversions
    for item in data.get("LineItems", []):
        # dates: ensure ISO (model should already do this)
        # money fields:
        for fld in ("Debit", "Credit", "Balance"):
            item[fld] = parse_money_to_float(item.get(fld))
    return data

def main():
    # 1) load OCR text
    if not os.path.isfile(RAW_TXT):
        print("❌ Raw text not found:", RAW_TXT)
        sys.exit(1)
    with open(RAW_TXT, "r", encoding="utf-8") as f:
        raw = f.read()

    print("▶️  Classifying OCR output…")
    result = llama_classify(raw)

    print("▶️  Post-processing numbers…")
    final = post_process(result)

    # 2) write JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(RAW_TXT))[0]
    out_path = os.path.join(OUTPUT_DIR, f"{base}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2)

    print(f"\n✅  Done! Output saved to:\n   {out_path}")
    print(json.dumps(final, indent=2))

if __name__ == "__main__":
    main()
