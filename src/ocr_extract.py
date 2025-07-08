import os
import sys
import pdfplumber
import pytesseract
from PIL import Image
from tqdm import tqdm

# 1) Point at your PDF directly  
SCRIPT_DIR = os.path.dirname(__file__)
PDF_PATH   = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "pdfs", "Easy life[1].pdf"))

# 2) Configure Tesseract  
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    pages = []
    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in tqdm(pdf.pages, desc="OCR pages", unit="pg"):
                img = page.to_image(resolution=200).original
                pages.append(pytesseract.image_to_string(img))
    else:
        img = Image.open(file_path)
        pages.append(pytesseract.image_to_string(img))
    return "\n".join(pages)

def main():
    if not os.path.isfile(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        sys.exit(1)

    print(f"▶️  OCR’ing '{PDF_PATH}' …")
    raw_text = extract_text(PDF_PATH)

    base   = os.path.splitext(os.path.basename(PDF_PATH))[0]
    out_txt = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "texts", f"{base}_raw.txt"))

    os.makedirs(os.path.dirname(out_txt), exist_ok=True)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(raw_text)

    print(f"\n✅  Raw OCR text saved to:\n   {out_txt}")

if __name__ == "__main__":
    main()
