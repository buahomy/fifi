# Ignis OS — ICS-204 Form Extractor

A small web app that turns **ICS-204 Assignment List forms** into a clean, sortable **CSV**.

Upload photos or scans of ICS-204 forms (typed or handwritten), and Google Gemini reads them and pulls out every field: incident info, supervisors, resources, tasks, comms and approvals. You can preview the results in the browser, then download one combined CSV for all the forms.

---

## What it does

1. **Upload:** drag and drop one or many forms (`.png`, `.jpg`, `.jpeg`, `.pdf`, up to 32 MB per upload).
2. **Extract:** each file is sent to Gemini with a fixed ICS-204 schema, so the output is consistent structured data instead of loose text.
3. **Organize:** the nested form data is flattened into **one row per resource**, plus one row per communication entry, so it's easy to filter, sort or pivot in Excel or Google Sheets.
4. **Flag:** each row gets a `status` so understaffed resources stand out.
5. **Download:** get a single timestamped CSV, `ics204_extracted_YYYYMMDD_HHMMSS.csv`.

---

## Quick start

**Requirements:** Python 3.10+ and a Gemini API key (free from [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
# 1. Clone and enter the project
git clone https://github.com/buahomy/fifi.git
cd fifi

# 2. Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Add your Gemini API key
echo "GOOGLE_API_KEY=your-key-here" > .env

# 4. Run the web app
python3 app.py
```

Open **http://localhost:8080** in your browser.

> The API key stays on the server in `.env` (which is git-ignored). People using the website never see or enter it. `GEMINI_API_KEY` also works as the variable name.

### Optional settings

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | *(required)* | Gemini API key |
| `PORT` | `8080` | Port the server listens on |
| `FLASK_DEBUG` | `0` | Set to `1` for auto-reload while developing |

---

## CSV output

Each row repeats the form's header info, so every row makes sense on its own when sorted or filtered.

| Group | Columns |
|---|---|
| **Source** | `source_image` |
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
| `CRITICAL` | Resource has fewer than 2 personnel (including 0 or missing) |
| `NO_RESOURCES` | Form has no resources listed |
| `COMMUNICATION` | Row is a communications-plan entry, not a resource |

---

## API

The web page uses two endpoints, which you can also call directly. Both take a `multipart/form-data` POST with one or more `files` fields.

| Endpoint | Returns |
|---|---|
| `POST /api/preview` | JSON: `records`, `record_count`, `files_processed`, `errors`, and the `raw` extracted data per file |
| `POST /api/extract` | The combined CSV file as a download |

```bash
curl -F "files=@form1.jpg" -F "files=@form2.pdf" \
  http://localhost:8080/api/extract -o ics204.csv
```

---

## Project structure

```
app.py                  Flask web app (upload, preview, CSV download)
templates/index.html    Upload page UI
ics204_extractor.py     Gemini extraction schema + flattening to rows (also runnable as a CLI)
main.py                 Batch processor with rate-limit retries, handwriting detection and confidence scores
image_text_extractor.py Early prototype: plain-text OCR of images
input_forms/            Sample ICS-204 form images
```

### Command-line batch modes

Besides the website, there are two scripts for processing a whole folder of images:

- `python3 ics204_extractor.py` writes combined Excel, CSV and JSON output. See [README_ICS204.md](README_ICS204.md).
- `python3 main.py` is a free-tier-friendly batch run over `input_forms/` that adds handwriting flags, confidence scores and a staffing analysis. See [README_Production.md](README_Production.md).

---

## Notes and limitations

- **Accuracy:** Gemini is strong at reading handwriting, but it can still misread smudged, crossed-out or faint entries. Review the CSV before using it for operational decisions.
- **Privacy:** uploaded forms are sent to Google's Gemini API for processing. Don't upload forms with sensitive personal information unless your Gemini terms allow it.
- **Rate limits:** free-tier Gemini keys have per-minute limits. For large batches, use `main.py`, which retries automatically.
- **Model:** set in `ics204_extractor.py` (currently `gemini-3.1-pro-preview`).
