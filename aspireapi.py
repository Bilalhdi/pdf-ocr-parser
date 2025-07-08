import requests
import json
import sys
import re

def correct_merchant(rcpt: dict) -> dict:
    """
    If merchant_name was mis-detected as 'Statement of Account',
    try to pull the real name from the OCR text.
    """
    name = rcpt.get("merchant_name", "")
    if name.strip().lower() == "statement of account":
        text = rcpt.get("ocr_text", "")
        m = re.search(r'Customer\s+([A-Z][A-Za-z0-9 &.,\-]+)', text)
        if m:
            rcpt["merchant_name"] = m.group(1).strip()
    return rcpt

def ocr_receipt(image_path, api_key="TEST", recognizer="auto", ref_no=None):
    """
    Send a receipt image to Asprise OCR and return the parsed JSON.
    """
    endpoint = 'https://ocr.asprise.com/api/v1/receipt'
    data = {
        'api_key': api_key,
        'recognizer': recognizer,
    }
    if ref_no:
        data['ref_no'] = ref_no

    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(endpoint, data=data, files=files)
            resp.raise_for_status()
    except FileNotFoundError:
        print(f"Error: file not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        return resp.json()
    except json.JSONDecodeError:
        print("Error: response is not valid JSON:", resp.text, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Asprise Receipt OCR Demo")
    parser.add_argument("image", help="Path to receipt image (jpg, png, pdf)")
    parser.add_argument("--api_key", default="TEST", help="Your Asprise API key")
    parser.add_argument(
        "--recognizer", default="auto",
        choices=["auto","US","CA","JP","SG"],
        help="Which country model to use"
    )
    parser.add_argument("--ref_no", help="Optional reference code")
    args = parser.parse_args()

    print("=== Python Receipt OCR Demo ===")
    result = ocr_receipt(
        image_path=args.image,
        api_key=args.api_key,
        recognizer=args.recognizer,
        ref_no=args.ref_no
    )

    # ── Post-process merchant_name ──
    for i, rcpt in enumerate(result.get("receipts", [])):
        result["receipts"][i] = correct_merchant(rcpt)
    # ── end correction ──

    receipts = result.get("receipts", [])
    if not receipts:
        print("❗ No receipts found in the response.")
        sys.exit(0)

    for idx, rcpt in enumerate(receipts, start=1):
        print(f"\n=== Receipt #{idx} ===")
        print(f"Merchant : {rcpt.get('merchant_name')}")
        print(f"Date     : {rcpt.get('date')}")
        print(f"Receipt# : {rcpt.get('receipt_no')}")
        print(f"Total    : {rcpt.get('total')} {rcpt.get('currency')}")
        print("Items:")
        for item in rcpt.get("items", []):
            desc = item.get("description", "").replace("\n", " ").strip()
            qty  = item.get("qty")
            amt  = item.get("amount")
            # Safe formatting: fall back to empty string if None
            qty_str = f"{qty}" if qty is not None else ""
            amt_str = f"{amt}" if amt is not None else ""
            print(f"  - {desc:<40}  qty={qty_str:<3}  amt={amt_str}")
