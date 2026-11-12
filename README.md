# Ignis OS — ICS-204 Form Extractor

A web app that turns **ICS-204 Assignment List forms** into a clean, sortable **CSV**.

Upload photos, scans or PDFs of ICS-204 forms (typed or handwritten). Google Gemini reads every field (incident info, supervisors, resources, tasks, comms and approvals), and the site shows the results in a table you can download as one combined CSV.

**Built with:** Python · Flask · Google Gemini API (structured JSON output) · vanilla JavaScript · Vercel

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

Open **http://localhost:8080** and paste your Gemini key into the page.

Settings go in environment variables, or in a git-ignored `.env` file locally:

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | *(unset)* | The owner's key, used for private-access visitors |
| `ACCESS_CODE` | *(unset)* | Secret code that unlocks the owner's key. **Always set this when `GOOGLE_API_KEY` is set on a public site**; without it, every visitor uses the owner's key. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model used for extraction |
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

The repo is ready for **[Vercel](https://vercel.com)**: import it at vercel.com/new, add the two environment variables above if you want private access, and deploy. Vercel detects the Flask app in `app.py` and serves `public/index.html` as the home page. A detailed form takes Gemini 30–60 seconds, which is well within Vercel's default 300-second request limit.

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

---

## Project structure

```
app.py               Flask server: serves the page and the /api endpoints
ics204_extractor.py  Gemini prompt + JSON schema, and flattening to CSV rows
public/index.html    The whole front end (upload, key handling, preview, CSV export)
requirements.txt     flask, google-genai
```

## Notes

- **Accuracy:** Gemini reads handwriting well, but smudged or crossed-out entries can be misread. Review the CSV before using it for operational decisions.
- **Privacy:** forms are sent to Google's Gemini API and are not saved by this app. Don't upload forms with sensitive personal information unless your Gemini terms allow it.
- **Limits:** uploads are capped at 4 MB per form after resizing. Free Gemini keys have per-minute rate limits; if you hit one, wait a minute and press Extract again, and only the failed forms are retried.
