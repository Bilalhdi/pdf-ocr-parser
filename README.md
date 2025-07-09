# PDF Invoice Parser API

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)  
![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey)  
![Tesseract](https://img.shields.io/badge/Tesseract-OCR-green)  
![Gemini](https://img.shields.io/badge/Google-Gemini_AI-yellow)

A high-performance REST API for extracting structured data from PDF invoices using OCR (Tesseract) and AI (Google Gemini).

## Table of Contents
- [Features](#features)  
- [Prerequisites](#prerequisites)  
- [Installation](#installation)  
- [Configuration](#configuration)  
- [API Usage](#api-usage)  
- [How It Works](#how-it-works)  
- [Deployment](#deployment)  
- [Limitations](#limitations)  
- [License](#license)  

## Features
- **AI-Powered Parsing** – Infers JSON schema and fills invoice fields via Google Gemini.  
- **OCR Processing** – Supports scanned PDFs using high-resolution Tesseract OCR.  
- **Chunked & Parallel** – Splits large docs into overlapping chunks and processes concurrently.  
- **Schema Inference** – Builds a JSON “mold” from sample text before extraction.  
- **Footer Extraction** – Extracts summary fields (totals, balances, ageing buckets).  
- **Secure API** – Key-based auth via `X-API-KEY` header.

## Prerequisites

### System Requirements
- **Tesseract OCR** installed and on your `PATH` (or specify via `TESSERACT_CMD`).  
- **Python 3.9+**

### Python Packages  
Listed in `requirements.txt`:
```python
Flask>=3.0
pdfplumber
pytesseract
google-generativeai
python-dotenv
```

## Installation

1. **Clone the repository**  
   ```python
   git clone https://github.com/<your-username>/pdf-ocr-parser.git
   cd pdf-ocr-parser
   ```

2. **(Optional) Create & activate a virtual environment**  
   ```python
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   .venv\Scripts\activate       # Windows
   ```

3. **Install dependencies**  
   ```python
   pip install -r requirements.txt
   ```

## Configuration

1. **Copy the example environment file**  
   ```python
   cp .env.example .env
   ```

2. **Edit `.env` and set your keys**  
   ```python
   FLASK_API_KEY=your_flask_api_key_here
   GEMINI_API_KEY=your_google_gemini_api_key_here
   TESSERACT_CMD=/usr/bin/tesseract   # or full path on Windows
   ```

## API Usage

### Start the Server
```python
python app.py
# or
flask run --host=0.0.0.0 --port=5000
```

### Endpoints

- **POST** `/parse`  
  Upload a PDF to parse:
  ```python
  curl -X POST http://localhost:5000/parse \
    -H "X-API-KEY: $FLASK_API_KEY" \
    -F "file=@invoice.pdf"
  ```
  **Response**:
  ```python
  {
    "parsed": "{...combined JSON output...}"
  }
  ```

- **GET** `/parse`  
  Retrieve the last parsed result (plain text):
  ```python
  curl http://localhost:5000/parse \
    -H "X-API-KEY: $FLASK_API_KEY"
  ```

## How It Works

1. **OCR Extraction**  
   Uses `pdfplumber` to render each page as an image, then Tesseract to extract text.  
2. **Text Chunking**  
   Splits raw text into overlapping chunks to respect model limits.  
3. **Schema Inference**  
   Sends the first chunk to Gemini to generate a JSON schema (keys only, values = `null`).  
4. **Parallel Parsing**  
   Submits each chunk + schema to Gemini across threads to populate values.  
5. **Footer Parsing**  
   Sends the final chunk to Gemini to extract summary fields (totals, balances).  
6. **Assembly**  
   Combines all chunk outputs and footer JSON into one cohesive response.

## Deployment

### Production with Gunicorn
```python
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker
Create a `Dockerfile`:
```python
FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN apt-get update && apt-get install -y tesseract-ocr
RUN pip install -r requirements.txt
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```
Build & run:
```python
docker build -t pdf-parser .
docker run \
  -e FLASK_API_KEY=your_flask_api_key_here \
  -e GEMINI_API_KEY=your_google_gemini_api_key_here \
  -e TESSERACT_CMD=tesseract \
  -p 5000:5000 pdf-parser
```

## Limitations
- **Temporary Storage**: Only the last parsed output is retained in memory; server restarts clear history.  
- **Cost & Rate Limits**: Google Gemini API usage may incur fees and rate limits.  
- **OCR Accuracy**: Depends on PDF quality; complex layouts may require pre-processing.  
- **Security**: API key sent in plain headers—use HTTPS and rotate keys in production.

## License
This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
