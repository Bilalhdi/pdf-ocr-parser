import re
import json


def clean_embedded_newlines(raw: str) -> str:
    """
    Remove actual newline characters only inside JSON string literals.
    """
    result = []
    in_string = False
    escape = False

    for c in raw:
        if escape:
            result.append(c)
            escape = False
        elif c == '\\':
            result.append(c)
            escape = True
        elif c == '"':
            result.append(c)
            in_string = not in_string
        elif in_string and c in ('\n', '\r'):
            # Skip actual newlines inside quoted strings
            continue
        else:
            result.append(c)

    return "".join(result)


def convert_txt_to_json(input_file: str, output_file: str):
    """
    1) Read raw .txt
    2) Remove any literal "\\n" or "\\r" via regex
    3) Clean embedded newlines inside strings
    4) Trim trailing incomplete data after last '}'
    5) Wrap in array if missing
    6) Parse and write prettified JSON
    """
    try:
        # 1) Read raw text
        with open(input_file, 'r', encoding='utf-8') as f:
            raw = f.read()

        # 2) Remove literal \n or \r escapes
        raw = re.sub(r'\\n|\\r', '', raw)

        # 3) Clean real newlines in quoted strings
        clean = clean_embedded_newlines(raw)

        # 4) Trim after last complete object
        last = clean.rfind('}')
        if last == -1:
            raise ValueError("No closing '}' found in input!")
        trimmed = clean[:last+1].rstrip()

        # 5) Ensure array closure
        if trimmed.lstrip().startswith('['):
            json_text = trimmed + "\n]\n"
        else:
            json_text = "[\n" + trimmed + "\n]\n"

        # 6) Parse and write
        data = json.loads(json_text)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Converted {input_file} → {output_file}")

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    input_txt = r"C:\Users\bilal\OneDrive\Desktop\Agile\ocr stuff\scripts\output\Easy life[1].txt"
    output_json = r"C:\Users\bilal\OneDrive\Desktop\Agile\ocr stuff\json outputs\Easy life[1].json"
    convert_txt_to_json(input_txt, output_json)


if __name__ == "__main__":
    main()
