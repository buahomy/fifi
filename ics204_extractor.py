"""
ICS-204 extraction: send one form (image or PDF) to Gemini with a fixed JSON
schema, then flatten the nested result into CSV-ready rows.
"""

import json
import os
import time

from google import genai
from google.genai import types

# Visitors using their own (often free-tier) key: fast, free-tier-friendly Flash.
# LOW thinking is about 10x faster than HIGH on Flash and gave identical results on test forms.
PUBLIC_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
PUBLIC_THINKING = os.environ.get("GEMINI_THINKING", "LOW")

# Private-access visitors using the owner's key: the owner's original Pro setup.
OWNER_MODEL = os.environ.get("OWNER_GEMINI_MODEL", "gemini-3.1-pro-preview")
# LOW, not HIGH: with the legibility instructions, HIGH took 25.6 s and ~$0.055 per page versus
# 12.2 s and ~$0.024 on LOW, with identical rows and the same hard-to-read rows flagged (2026-11-12).
OWNER_THINKING = os.environ.get("OWNER_GEMINI_THINKING", "LOW")

# Preview models (like gemini-3.1-pro-preview) are only served on v1beta.
API_VERSION = "v1beta"

PROMPT = (
    "First decide whether this page is an ICS-204 Assignment List (also titled 'Work Assignment' "
    "or 'Division/Group Assignment List'). Set is_ics204 and detected_form accordingly. If it is "
    "not an ICS-204, return empty sections.\n"
    "If it is, extract all data and structure it as JSON. Carefully read every field, including "
    "the incident header, resources assigned, work assignments, communications plan and approval "
    "section. Include handwritten entries and corrections. If a field is empty or not visible, "
    "use an empty string.\n"
    "Legibility: for every resource and communications row, set legibility to 'clear' when you are "
    "sure of every value, 'uncertain' when any handwritten value is hard to read and you are giving "
    "your best reading, or 'illegible' when you cannot read it. For uncertain or illegible rows, "
    "write review_note naming the field and the problem (e.g. 'num_persons: 3 or 8, smudged'). "
    "List any unclear header, work-assignment or approval fields in unclear_fields. Never guess "
    "silently: if you are not sure, flag it."
)

LEGIBILITY = ["clear", "uncertain", "illegible"]

# Column order of the CSV. Every row has every column, so the file lines up cleanly.
COLUMNS = [
    "source_file", "incident_name", "operational_period", "date_from", "date_to",
    "branch", "division_group",
    "operations_chief", "branch_director", "div_group_supervisor", "air_attack_supervisor",
    "resource_designator", "resource_leader", "num_persons", "resource_lwd", "drop_off", "pick_up",
    "task", "purpose", "end_state", "special_instructions",
    "comm_function", "comm_channel", "comm_rx_frequency", "comm_rx_tone",
    "comm_tx_frequency", "comm_tx_tone", "comm_mode",
    "prepared_by", "approved_by", "approval_date", "approval_time",
    "status",
    # Human-review flags (Gemini's own judgment of handwriting, not a measured probability)
    "needs_review", "legibility", "review_note", "form_review_note",
]


def _schema(kind):
    if kind == "LEGIBILITY":
        return types.Schema(type=types.Type.STRING, enum=LEGIBILITY)
    return types.Schema(type=kind)


def _obj(fields, required=None):
    return types.Schema(
        type=types.Type.OBJECT,
        required=required,
        properties={name: _schema(kind) for name, kind in fields.items()},
    )


def _strings(*names):
    return {name: types.Type.STRING for name in names}


_REVIEW = {"legibility": "LEGIBILITY", "review_note": types.Type.STRING}


RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["is_ics204", "detected_form", "incident_header", "resources_assigned", "work_assignments"],
    properties={
        "is_ics204": types.Schema(type=types.Type.BOOLEAN),
        "detected_form": types.Schema(type=types.Type.STRING),
        "unclear_fields": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
        "incident_header": _obj(_strings(
            "incident_name", "operational_period", "date_from", "date_to", "branch", "division_group")),
        "operations_personnel": _obj(_strings(
            "div_group_supervisor", "branch_director", "air_attack_supervisor", "operations_chief")),
        "resources_assigned": types.Schema(
            type=types.Type.ARRAY,
            items=_obj({**_strings("designator", "lwd", "leader", "drop_off", "pick_up"),
                        "num_persons": types.Type.INTEGER, **_REVIEW}, required=["legibility"]),
        ),
        "work_assignments": _obj(_strings("task", "purpose", "end_state")),
        "special_instructions": types.Schema(type=types.Type.STRING),
        "communications_plan": types.Schema(
            type=types.Type.ARRAY,
            items=_obj({**_strings("function", "channel", "rx_frequency", "rx_tone",
                                   "tx_frequency", "tx_tone", "mode"), **_REVIEW}, required=["legibility"]),
        ),
        "approval": _obj(_strings("prepared_by", "approved_by", "date", "time")),
    },
)


# Official Gemini API paid-tier prices, USD per 1M tokens (output includes thinking tokens).
# Source: https://aistudio.google.com/docs/pricing, read 2026-11-12. Update when Google changes them.
PRICING = {
    "gemini-3.8-flash": {
        "label": "Gemini 3.8 Flash", "free_tier": True,
        "rates": [  # (valid from, input, output)
            ("2000-01-01", 0.75, 3.75),
            ("2027-01-01", 1.50, 7.50),
        ],
    },
    "gemini-3.1-pro-preview": {
        "label": "Gemini 3.1 Pro Preview", "free_tier": False,
        "rates": [("2000-01-01", 2.00, 12.00)],  # prompts <= 200k tokens (every ICS-204 is ~1.2k)
    },
}
PRICING_SOURCE = {"url": "https://aistudio.google.com/docs/pricing", "read": "2026-11-12"}


def current_rates(model: str, today: str | None = None):
    """(input, output) USD per 1M tokens in effect today, or None if the model isn't priced here."""
    info = PRICING.get(model)
    if not info:
        return None
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    rate = [r for r in info["rates"] if r[0] <= today][-1]
    return rate[1], rate[2]


def usage_summary(response, model: str, seconds: float) -> dict:
    """Tokens, time and estimated paid-tier cost for one Gemini call."""
    u = response.usage_metadata
    tokens_in = u.prompt_token_count or 0
    tokens_out = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
    rates = current_rates(model)
    cost = round((tokens_in * rates[0] + tokens_out * rates[1]) / 1e6, 5) if rates else None
    return {"model": model, "calls": 1, "seconds": round(seconds, 1),
            "tokens_in": tokens_in, "tokens_out": tokens_out, "est_cost_usd": cost}


def extract_form(client: genai.Client, data: bytes, mime_type: str, model: str, thinking: str):
    """Send one form to Gemini (exactly one API call). Returns (parsed JSON, usage). Raises on API errors."""
    started = time.time()
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[
            types.Part.from_text(text=PROMPT),
            types.Part.from_bytes(data=data, mime_type=mime_type),
        ])],
        config=types.GenerateContentConfig(
            top_p=0.1,
            thinking_config=types.ThinkingConfig(thinking_level=thinking),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    return json.loads(response.text), usage_summary(response, model, time.time() - started)


def staffing_status(num_persons) -> str:
    if not num_persons:
        return "NO_PERSONNEL"
    if num_persons < 2:
        return "CRITICAL"
    return "OK"


def flatten(data: dict, source_file: str) -> list[dict]:
    """One row per resource, plus one row per communications-plan entry."""
    header = data.get("incident_header") or {}
    ops = data.get("operations_personnel") or {}
    work = data.get("work_assignments") or {}
    approval = data.get("approval") or {}

    base = dict.fromkeys(COLUMNS, "")
    base.update({
        "source_file": source_file,
        "incident_name": header.get("incident_name", ""),
        "operational_period": header.get("operational_period", ""),
        "date_from": header.get("date_from", ""),
        "date_to": header.get("date_to", ""),
        "branch": header.get("branch", ""),
        "division_group": header.get("division_group", ""),
        "operations_chief": ops.get("operations_chief", ""),
        "branch_director": ops.get("branch_director", ""),
        "div_group_supervisor": ops.get("div_group_supervisor", ""),
        "air_attack_supervisor": ops.get("air_attack_supervisor", ""),
        "task": work.get("task", ""),
        "purpose": work.get("purpose", ""),
        "end_state": work.get("end_state", ""),
        "special_instructions": data.get("special_instructions", ""),
        "prepared_by": approval.get("prepared_by", ""),
        "approved_by": approval.get("approved_by", ""),
        "approval_date": approval.get("date", ""),
        "approval_time": approval.get("time", ""),
        "form_review_note": "; ".join(str(f) for f in (data.get("unclear_fields") or []) if f),
    })

    rows = []
    for res in data.get("resources_assigned") or []:
        num = res.get("num_persons") or 0
        rows.append({**base, **review_flags(res),
                     "resource_designator": res.get("designator", ""),
                     "resource_leader": res.get("leader", ""),
                     "num_persons": num,
                     "resource_lwd": res.get("lwd", ""),
                     "drop_off": res.get("drop_off", ""),
                     "pick_up": res.get("pick_up", ""),
                     "status": staffing_status(num)})
    if not rows:
        rows.append({**base, "status": "NO_RESOURCES"})

    for comm in data.get("communications_plan") or []:
        rows.append({**base, **review_flags(comm),
                     "comm_function": comm.get("function", ""),
                     "comm_channel": comm.get("channel", ""),
                     "comm_rx_frequency": comm.get("rx_frequency", ""),
                     "comm_rx_tone": comm.get("rx_tone", ""),
                     "comm_tx_frequency": comm.get("tx_frequency", ""),
                     "comm_tx_tone": comm.get("tx_tone", ""),
                     "comm_mode": comm.get("mode", ""),
                     "status": "COMMUNICATION"})
    return rows


def review_flags(item: dict) -> dict:
    """needs_review = YES when Gemini says a row's handwriting was uncertain or illegible."""
    legibility = str(item.get("legibility") or "").lower()
    if legibility not in LEGIBILITY:
        legibility = ""
    return {
        "legibility": legibility,
        "needs_review": "YES" if legibility in ("uncertain", "illegible") else "",
        "review_note": item.get("review_note", "") if legibility != "clear" else "",
    }
