"""
Ignis OS: ICS-204 Form Extractor web app.

Visitors either bring their own Gemini API key (sent per request in the
X-Gemini-Key header, never stored) or, if they were given the private access
code, use the owner's key stored on the server (GOOGLE_API_KEY / GEMINI_API_KEY).

If ACCESS_CODE is set, the server key is used only for requests carrying a
matching X-Access-Code header. If ACCESS_CODE is not set, the server key is an
open fallback, which is handy locally but must not be used on a public site.
"""

import hmac
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


def access_code():
    return os.environ.get("ACCESS_CODE", "").strip()


def code_matches(supplied: str) -> bool:
    expected = access_code()
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def resolve_key():
    """Return (api_key, error_message). Visitor's own key wins; otherwise the server key if allowed."""
    own = request.headers.get("X-Gemini-Key", "").strip()
    if own:
        return own, None
    if not server_key():
        return None, "Add your Gemini API key first."
    if access_code() and not code_matches(request.headers.get("X-Access-Code", "").strip()):
        return None, "Add your Gemini API key, or open your private access link again."
    return server_key(), None


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/api/config")
def config():
    return jsonify({
        "server_key": bool(server_key()),
        "access_code_required": bool(server_key() and access_code()),
        "columns": COLUMNS,
        "max_upload_mb": MAX_UPLOAD_MB,
    })


@app.post("/api/access")
def check_access():
    """Lets the page confirm an access code before saving it."""
    ok = bool(server_key()) and code_matches(request.headers.get("X-Access-Code", "").strip())
    return jsonify({"ok": ok}), (200 if ok else 401)


@app.post("/api/extract")
def extract():
    api_key, problem = resolve_key()
    if problem:
        return jsonify({"error": problem}), 401

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
