#!/usr/bin/env python3
"""
Ignis OS — ICS-204 Form Extractor Web App
Upload PNG, JPG, or PDF forms, extract structured data with Gemini Pro, download CSV.
"""

import io
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from google import genai

from ics204_extractor import extract_ics204_data_from_bytes, flatten_ics204_data

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def load_env_file():
    """Load GOOGLE_API_KEY from .env in project root if present."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


def get_api_key():
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def get_client():
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "API key not set. Add GOOGLE_API_KEY to .env or export it before starting the server."
        )
    return genai.Client(api_key=api_key)


def allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def records_to_csv_bytes(records):
    df = pd.DataFrame(records)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer


def process_uploads(files):
    client = get_client()
    all_records = []
    raw_results = {}
    errors = []

    for upload in files:
        filename = upload.filename
        file_bytes = upload.read()

        try:
            extracted = extract_ics204_data_from_bytes(client, file_bytes, filename)
            raw_results[filename] = extracted
            if "error" in extracted:
                errors.append({
                    "file": filename,
                    "error": extracted.get("error"),
                    "details": extracted.get("details", ""),
                })
            else:
                all_records.extend(flatten_ics204_data(extracted, filename))
        except Exception as e:
            errors.append({"file": filename, "error": str(e)})

    return all_records, raw_results, errors


@app.route("/")
def index():
    return render_template("index.html", api_configured=bool(get_api_key()))


@app.route("/api/extract", methods=["POST"])
def extract():
    if not get_api_key():
        return jsonify({"error": "GOOGLE_API_KEY is not configured"}), 500

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files uploaded"}), 400

    valid_files = [f for f in files if f.filename and allowed_file(f.filename)]
    if not valid_files:
        return jsonify({"error": "Invalid file type. Supported formats: PNG, JPG, PDF"}), 400

    try:
        all_records, raw_results, errors = process_uploads(valid_files)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    if not all_records:
        return jsonify({
            "error": "No ICS-204 data could be extracted from the uploaded files.",
            "errors": errors,
            "raw": raw_results,
        }), 422

    csv_buffer = records_to_csv_bytes(all_records)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"ics204_extracted_{timestamp}.csv"

    return send_file(
        csv_buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=csv_filename,
    )


@app.route("/api/preview", methods=["POST"])
def preview():
    if not get_api_key():
        return jsonify({"error": "GOOGLE_API_KEY is not configured"}), 500

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files uploaded"}), 400

    valid_files = [f for f in files if f.filename and allowed_file(f.filename)]
    if not valid_files:
        return jsonify({"error": "Invalid file type. Supported formats: PNG, JPG, PDF"}), 400

    try:
        all_records, raw_results, errors = process_uploads(valid_files)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "records": all_records,
        "record_count": len(all_records),
        "files_processed": len(valid_files),
        "errors": errors,
        "raw": raw_results,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"Ignis OS ICS-204 Extractor — http://localhost:{port}")
    if not get_api_key():
        print("Warning: GOOGLE_API_KEY not set. Add it to .env before uploading forms.")
    app.run(host="0.0.0.0", port=port, debug=debug)
