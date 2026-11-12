# 🔥 fifi — Fire Incident Form Intelligence

**Live:** https://fifi-tan.vercel.app

A web app that turns **ICS-204 Assignment List forms** into a clean, sortable **CSV**, and places those incidents on a **live map of US wildfires**.

Upload photos, scans or PDFs of ICS-204 forms (typed or handwritten). Google Gemini reads every field (incident info, supervisors, resources, tasks, comms and approvals), and the site shows the results in a table you can download as one combined CSV.

**Built with:** Python · Flask · Google Gemini API (structured JSON output) · MapLibre GL JS · vanilla JavaScript · Vercel

## Live fire map

The landing page (`/`) shows a live operating picture, built entirely from public, keyless feeds:

| Layer | Source | Notes |
|---|---|---|
| Incidents | NIFC WFIGS current incident locations | Sized by acres, colored by containment. Popups show personnel, complexity, cause, behavior and estimated cost. |
| Perimeters | NIFC WFIGS current interagency perimeters | Simplified to ~100 m for a light payload |
| Satellite hotspots | NASA FIRMS VIIRS, NOAA-20 + NOAA-21, trailing 24 h | Colored by fire radiative power. Heatmap at continental zoom, points up close. Relayed by `/api/hotspots`. |
| Your ICS-204s | Your own extractions, kept in your browser | Matched to the national feed by incident name; gold ring plus your form totals in the popup |
| Imagery | Esri World Imagery | Optional basemap |

Filters: wildfire / prescribed, minimum acres, state, name search, hide contained, minimum fire power (MW) and detection confidence. One filter pass drives the map, the list and every counter.

The fire-power color ramp, the intensity and confidence filters, and the heatmap-to-points crossfade are adapted from the MIT-licensed [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view).

## Security & privacy

- **No storage:** there is no database and no file storage. Uploaded forms are held **in memory only** for the request (`InMemoryRequest` in `app.py` stops Werkzeug spooling large uploads to disk), then discarded.
- **Visitor keys:** sent per request in `X-Gemini-Key`, used for that one Gemini call, never logged or saved. Kept in the visitor's browser only if they tick "Remember on this device".
- **Private access:** the owner's key is a host environment variable and never reaches the browser; only the access code does.
- **Results stay client-side:** the CSV is built in the browser, and the map summary lives in the browser's `localStorage` until cleared.
- **Google:** Gemini necessarily receives each form. On free-tier keys Google may use content to improve its products; paid keys are not used for training. Use a paid key for confidential IAPs.

---

## How it works

1. **Get access, either way:**
   - **Bring your own key:** visitors paste their own free [Gemini API key](https://aistudio.google.com/apikey). It's sent only with their own requests (in the `X-Gemini-Key` header) and is never stored on the server. They can choose to remember it in their own browser.
   - **Private access link:** people you trust open `https://your-site/?access=YOUR_CODE` and use the site owner's key with no setup. The code is checked on the server and remembered in their browser, and the owner's key never leaves the server. See [Private access](#private-access).
2. **Upload:** drag and drop forms (`.jpg`, `.png`, `.webp`, `.pdf`). Large photos are resized in the browser before upload, so phone pictures work fine.
3. **Extract:** forms are sent one at a time to Gemini with a fixed ICS-204 JSON schema, so the output has the same structure every time.
4. **Organize:** each form is flattened into **one row per resource**, plus one row per communications-plan entry. Every row carries the form's header info, so it still makes sense after sorting or filtering.
5. **Download:** the CSV is built in the browser from the results, so nothing is processed twice.

---

## Run it locally

Requires Python 3.10+.

```bash
git clone https://github.com/buahomy/fifi.git
cd fifi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open **http://localhost:8080** for the landing page and live map, or **http://localhost:8080/extract** to paste your Gemini key and extract forms.

Settings go in environment variables, or in a git-ignored `.env` file locally:

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | *(unset)* | The owner's key, used for private-access visitors |
| `ACCESS_CODE` | *(unset)* | Secret code that unlocks the owner's key. **Always set this when `GOOGLE_API_KEY` is set on a public site**; without it, every visitor uses the owner's key. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model for visitors using their own key (free-tier friendly) |
| `GEMINI_THINKING` | `LOW` | Thinking level for that model. On Flash, `LOW` is about 10x faster than `HIGH` and matched it on test forms. |
| `OWNER_GEMINI_MODEL` | `gemini-3.1-pro-preview` | Model for private-access visitors using the owner's key |
| `OWNER_GEMINI_THINKING` | `HIGH` | Thinking level for the owner's model (about 15 s per form on Pro) |
| `PORT` | `8080` | Local server port |
| `FLASK_DEBUG` | `0` | `1` enables auto-reload |

## Private access

To let specific people (a professor, a teammate) use your key without giving it to them:

1. Pick a long random code, e.g. `openssl rand -hex 12`.
2. On your host, set `GOOGLE_API_KEY` to your key and `ACCESS_CODE` to the code.
3. Send them `https://your-site/?access=THE_CODE`.

Opening the link checks the code, saves it in their browser, and removes it from the address bar. After that they can just visit the site normally. Everyone else still needs their own key. To cut off access, change `ACCESS_CODE` and redeploy.

Usage through the link is billed to your Gemini key, so share it only with people you trust.

## Deploy

The repo is ready for **[Vercel](https://vercel.com)**: import it at vercel.com/new, add the two environment variables above if you want private access, and deploy. Vercel detects the Flask app in `app.py` and serves the landing page at `/` and the extractor at `/extract`. A form usually takes 10–20 seconds. Each Gemini call is capped at 240 seconds, so a slow response returns a clear "try again" message before Vercel's 300-second limit.

It also runs on any host that supports Python (Render, Railway, Fly.io, Cloud Run) with `gunicorn app:app`.

---

## CSV columns

| Group | Columns |
|---|---|
| **Source** | `source_file` |
| **Incident** | `incident_name`, `operational_period`, `date_from`, `date_to`, `branch`, `division_group` |
| **Operations personnel** | `operations_chief`, `branch_director`, `div_group_supervisor`, `air_attack_supervisor` |
| **Resource** | `resource_designator`, `resource_leader`, `num_persons`, `resource_lwd`, `drop_off`, `pick_up` |
| **Work assignment** | `task`, `purpose`, `end_state`, `special_instructions` |
| **Communications** | `comm_function`, `comm_channel`, `comm_rx_frequency`, `comm_rx_tone`, `comm_tx_frequency`, `comm_tx_tone`, `comm_mode` |
| **Approval** | `prepared_by`, `approved_by`, `approval_date`, `approval_time` |
| **Analysis** | `status` |

### `status` values

| Value | Meaning |
|---|---|
| `OK` | Resource has 2 or more personnel |
| `CRITICAL` | Resource has exactly 1 person |
| `NO_PERSONNEL` | Personnel count is 0 or missing |
| `NO_RESOURCES` | The form lists no resources |
| `COMMUNICATION` | Row is a communications-plan entry, not a resource |

---

## API

`POST /api/extract` takes `multipart/form-data` with one `file`, and optionally an `X-Gemini-Key` header. It returns `{"rows": [...]}`.

```bash
curl -H "X-Gemini-Key: $GEMINI_KEY" -F "file=@form.jpg" http://localhost:8080/api/extract
```

Instead of `X-Gemini-Key`, a request can send `X-Access-Code` to use the owner's key (see [Private access](#private-access)).

`GET /api/config` returns the CSV column order, the upload size limit, and whether the server key needs an access code. `POST /api/access` (with `X-Access-Code`) returns 200 if the code is valid and 401 if not.

`GET /api/hotspots` returns NASA FIRMS VIIRS detections (NOAA-20 + NOAA-21, trailing 24 h, US + Hawaii) as compact arrays: `[lon, lat, frp_mw, confidence, acquired_utc, daynight, satellite]`. Cached for 15 minutes.

---

## Project structure

```
app.py               Flask server: pages, /api endpoints, FIRMS relay, in-memory uploads
ics204_extractor.py  Gemini prompt + JSON schema, and flattening to CSV rows
public/index.html    Landing page + live fire map (MapLibre)
public/extract.html  Extractor (upload, key / access link, preview, CSV export)
requirements.txt     flask, google-genai
```

## Notes

- **Accuracy:** Gemini reads handwriting well, but smudged or crossed-out entries can be misread. Review the CSV before using it for operational decisions.
- **Privacy:** see [Security & privacy](#security--privacy).
- **Not for emergency use:** map feeds can be delayed or incomplete. Confirm with official sources and InciWeb.
- **Limits:** uploads are capped at 4 MB per form after resizing. Free Gemini keys have per-minute rate limits; if you hit one, wait a minute and press Extract again, and only the failed forms are retried.
