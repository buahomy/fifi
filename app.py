"""
Ignis OS: ICS-204 Form Extractor web app.

Each visitor uses their own Gemini API key (sent per request in the
X-Gemini-Key header, never stored). If GOOGLE_API_KEY / GEMINI_API_KEY is set on
the server, it is used as a fallback for visitors who don't provide one.
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai import errors as genai_errors

from ics204_extractor import COLUMNS, extract_form, flatten

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"

MIME_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".pdf": "application/pdf",
}
MAX_UPLOAD_MB = 4  # stays under serverless request limits; the page shrinks photos first


def load_env_file():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file()

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def server_key():
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/api/config")
def config():
    return jsonify({"server_key": bool(server_key()), "columns": COLUMNS, "max_upload_mb": MAX_UPLOAD_MB})


@app.post("/api/extract")
def extract():
    api_key = request.headers.get("X-Gemini-Key", "").strip() or server_key()
    if not api_key:
        return jsonify({"error": "Add your Gemini API key first."}), 401

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "No file uploaded."}), 400

    mime_type = MIME_TYPES.get(Path(upload.filename).suffix.lower())
    if not mime_type:
        return jsonify({"error": "Unsupported file type. Use PNG, JPG, WEBP or PDF."}), 400

    try:
        data = extract_form(genai.Client(api_key=api_key), upload.read(), mime_type)
    except genai_errors.ClientError as e:
        if e.code == 429:
            return jsonify({"error": "Gemini rate limit reached. Wait a minute and try again."}), 429
        if e.code in (400, 401, 403) and "API key" in str(e):
            return jsonify({"error": "Gemini rejected the API key. Check it and try again."}), 401
        return jsonify({"error": f"Gemini error: {e.message or e}"}), 502
    except genai_errors.APIError as e:
        return jsonify({"error": f"Gemini is unavailable right now ({e.code}). Try again shortly."}), 502
    except ValueError:
        return jsonify({"error": "Gemini returned data that couldn't be read. Try again."}), 502

    return jsonify({"rows": flatten(data, upload.filename)})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File is larger than {MAX_UPLOAD_MB} MB."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"ICS-204 Extractor: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
