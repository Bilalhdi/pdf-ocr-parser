import os
import sys
import pdfplumber
import pytesseract
from PIL import Image

# ——— Configuration ———
# Path to your PDF:
PDF_FILE = r"C:\Users\bilal\OneDrive\Desktop\Agile\ocr stuff\pdfs\Pharmanet.pdf"

# How many pages you want to extract (from page 1 up to this):
NUM_PAGES = 1

# Configure Tesseract:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_page_text(pdf_path, page_number):
    """
    OCR a single page (1-based) from the PDF and return its text.
    """
    with pdfplumber.open(pdf_path) as pdf:
        idx = page_number - 1
        if idx < 0 or idx >= len(pdf.pages):
            raise ValueError(f"PDF has {len(pdf.pages)} pages; cannot extract page {page_number}")
        page = pdf.pages[idx]
        img = page.to_image(resolution=200).original
        return pytesseract.image_to_string(img)

def main():
    # 1) Check file exists
    if not os.path.isfile(PDF_FILE):
        print(f"❌  File not found: {PDF_FILE}")
        sys.exit(1)

    # 2) Determine how many pages we'll actually loop over
    with pdfplumber.open(PDF_FILE) as pdf:
        total_pages = len(pdf.pages)
    pages_to_extract = min(NUM_PAGES, total_pages)
    print(f"▶️  Extracting OCR from pages 1–{pages_to_extract} of {PDF_FILE} (PDF has {total_pages} pages)…")

    # 3) OCR each page
    texts = []
    for pg in range(1, pages_to_extract + 1):
        print(f"   • page {pg}…", end=" ", flush=True)
        try:
            page_text = extract_page_text(PDF_FILE, pg)
            texts.append(page_text)
            print("✅")
        except Exception as e:
            print(f"❌  failed: {e}")

    # 4) Join and save
    full_text = "\n\n".join(texts)
    out_txt = f"{os.path.splitext(PDF_FILE)[0]}_pages1-{pages_to_extract}.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"\n✅  OCR text for pages 1–{pages_to_extract} saved to:\n    {out_txt}")

    # 5) Preview
    print("\n--- Raw text preview ---")
    preview = full_text[:500].replace("\n", " ")
    print(preview + ("…" if len(full_text) > 500 else ""))
    print("--- End preview ---")

if __name__ == "__main__":
    main()
