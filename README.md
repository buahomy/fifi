# Ignis OS — ICS-204 Form Extractor

A web app that turns **ICS-204 Assignment List forms** into a clean, sortable **CSV**.

Upload photos, scans or PDFs of ICS-204 forms (typed or handwritten). Google Gemini reads every field (incident info, supervisors, resources, tasks, comms and approvals), and the site shows the results in a table you can download as one combined CSV.

**Built with:** Python · Flask · Google Gemini API (structured JSON output) · vanilla JavaScript · Vercel

---

## How it works

1. **Bring your own key:** each visitor pastes their own free [Gemini API key](https://aistudio.google.com/apikey). It's sent only with that visitor's requests (in the `X-Gemini-Key` header) and is never stored on the server. Visitors can choose to remember it in their own browser.
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

**Optional shared key:** to skip pasting a key on your own machine, create a `.env` file containing `GOOGLE_API_KEY=your-key`. The `.env` file is git-ignored. When a server key is set, visitors who don't enter their own key will use it, so **don't set one on a public deployment** unless you're willing to pay for everyone's usage.

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | *(unset)* | Optional shared fallback key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model used for extraction |
| `PORT` | `8080` | Local server port |
| `FLASK_DEBUG` | `0` | `1` enables auto-reload |

## Deploy

The repo is ready for **[Vercel](https://vercel.com)**: import it at vercel.com/new, keep the default settings, and deploy. Vercel detects the Flask app in `app.py` and serves `public/index.html` as the home page. No environment variables are needed: visitors bring their own keys. A detailed form takes Gemini 30–60 seconds, which is well within Vercel's default 300-second request limit.

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

`GET /api/config` returns the CSV column order, the upload size limit, and whether a shared server key is configured.

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
