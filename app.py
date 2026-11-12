"""
Ignis OS: ICS-204 Form Extractor web app.

Visitors either bring their own Gemini API key (sent per request in the
X-Gemini-Key header, never stored) or, if they were given the private access
code, use the owner's key stored on the server (GOOGLE_API_KEY / GEMINI_API_KEY).

If ACCESS_CODE is set, the server key is used only for requests carrying a
matching X-Access-Code header. If ACCESS_CODE is not set, the server key is an
open fallback, which is handy locally but must not be used on a public site.
"""

import csv
import hmac
import io
import os
import ssl
import time
import urllib.request
from pathlib import Path

from flask import Flask, Request, jsonify, request, send_from_directory
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from ics204_extractor import (API_VERSION, COLUMNS, OWNER_MODEL, OWNER_THINKING,
                              PUBLIC_MODEL, PUBLIC_THINKING, extract_form, flatten)

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"

MIME_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".pdf": "application/pdf",
}
MAX_UPLOAD_MB = 4  # stays under serverless request limits; the page shrinks photos first
GEMINI_TIMEOUT_MS = 240_000  # give up before the host's 300 s limit so we can return a clear error


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

class InMemoryRequest(Request):
    """Keep uploaded forms in memory only.

    By default Werkzeug spools uploads over 500 KB to a temporary file on disk. Forms may
    be confidential, so they live only in RAM for the length of the request (max 4 MB).
    """

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        return io.BytesIO()


app = Flask(__name__, static_folder=None)
app.request_class = InMemoryRequest
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def server_key():
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def access_code():
    return os.environ.get("ACCESS_CODE", "").strip()


def code_matches(supplied: str) -> bool:
    expected = access_code()
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def resolve_key():
    """Return (api_key, uses_owner_key, error_message).

    The visitor's own key wins; otherwise the owner's server key, if the access code allows it.
    """
    own = request.headers.get("X-Gemini-Key", "").strip()
    if own:
        return own, False, None
    if not server_key():
        return None, False, "Add your Gemini API key first."
    if access_code() and not code_matches(request.headers.get("X-Access-Code", "").strip()):
        return None, False, "Add your Gemini API key, or open your private access link again."
    return server_key(), True, None


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/extract")
def extract_page():
    return send_from_directory(PUBLIC, "extract.html")


# NASA FIRMS satellite hotspots: VIIRS on NOAA-20 and NOAA-21, trailing 24 h, US + Hawaii.
# These public keyless CSVs don't allow browser cross-origin requests, so the server relays
# them in compact form. (Suomi NPP is left out: NASA stopped delivering it on 2026-11-02.)
FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
FIRMS_SOURCES = {
    "NOAA-20": f"{FIRMS_BASE}/noaa-20-viirs-c2/csv/J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
    "NOAA-21": f"{FIRMS_BASE}/noaa-21-viirs-c2/csv/J2_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
}
HOTSPOT_TTL_S = 900
_hotspot_cache = {"at": 0.0, "body": None}

try:  # certifi ships with google-genai's HTTP stack; some Python installs lack system CA certs
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


def _fetch_hotspots():
    points, sources = [], []
    for name, url in FIRMS_SOURCES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fifi-ics204"})
            with urllib.request.urlopen(req, timeout=20, context=_SSL) as resp:
                text = resp.read(32 * 1024 * 1024).decode("utf-8", "replace")
        except Exception:
            sources.append({"name": name, "ok": False})
            continue
        count = 0
        for row in csv.DictReader(io.StringIO(text)):
            try:
                points.append([
                    round(float(row["longitude"]), 4), round(float(row["latitude"]), 4),
                    round(float(row.get("frp") or 0), 1),
                    (row.get("confidence") or "")[:1].lower(),          # l / n / h
                    f'{row.get("acq_date", "")}T{(row.get("acq_time") or "").zfill(4)}Z',
                    row.get("daynight", ""), name,
                ])
                count += 1
            except (KeyError, ValueError):
                continue
        sources.append({"name": name, "ok": True, "count": count})
    if not any(s["ok"] for s in sources):
        return None
    return {
        "source": "NASA FIRMS · VIIRS NOAA-20 + NOAA-21 · trailing 24 h",
        "fetched": int(time.time()),
        "sources": sources,
        "fields": ["lon", "lat", "frp_mw", "confidence", "acquired_utc", "daynight", "satellite"],
        "points": points,
    }


@app.get("/api/hotspots")
def hotspots():
    cache = _hotspot_cache
    if cache["body"] is None or time.time() - cache["at"] > HOTSPOT_TTL_S:
        fresh = _fetch_hotspots()
        if fresh:
            cache.update(at=time.time(), body=fresh)
        elif cache["body"] is None:
            return jsonify({"error": "Satellite hotspot feed is unavailable right now."}), 502
    body = dict(cache["body"], stale=time.time() - cache["at"] > HOTSPOT_TTL_S * 2)
    response = jsonify(body)
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=900"
    return response


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
    api_key, owner, problem = resolve_key()
    if problem:
        return jsonify({"error": problem}), 401
    model, thinking = (OWNER_MODEL, OWNER_THINKING) if owner else (PUBLIC_MODEL, PUBLIC_THINKING)

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "No file uploaded."}), 400

    mime_type = MIME_TYPES.get(Path(upload.filename).suffix.lower())
    if not mime_type:
        return jsonify({"error": "Unsupported file type. Use PNG, JPG, WEBP or PDF."}), 400

    client = genai.Client(api_key=api_key, http_options=genai_types.HttpOptions(
        api_version=API_VERSION, timeout=GEMINI_TIMEOUT_MS))
    try:
        data = extract_form(client, upload.read(), mime_type, model, thinking)
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
    except Exception as e:  # network errors and timeouts from the HTTP client
        if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
            return jsonify({"error": "Gemini took too long on this form. Press Extract data to try again."}), 504
        return jsonify({"error": "Couldn't reach Gemini. Try again shortly."}), 502

    return jsonify({"rows": flatten(data, upload.filename), "model": model})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File is larger than {MAX_UPLOAD_MB} MB."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"ICS-204 Extractor: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
