"""
ICS-204 extraction: send one form (image or PDF) to Gemini with a fixed JSON
schema, then flatten the nested result into CSV-ready rows.
"""

import json
import os

from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# LOW is about 10x faster than HIGH and gave identical results on test forms;
# reading a form needs good vision, not long reasoning.
THINKING_LEVEL = os.environ.get("GEMINI_THINKING", "LOW")

PROMPT = (
    "Extract all data from this ICS-204 Work Assignment Form and structure it as JSON. "
    "Carefully read every field, including the incident header, resources assigned, "
    "work assignments, communications plan and approval section. Include handwritten "
    "entries and corrections. If a field is empty or not visible, use an empty string."
)

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
]


def _obj(fields, required=None):
    return types.Schema(
        type=types.Type.OBJECT,
        required=required,
        properties={name: types.Schema(type=kind) for name, kind in fields.items()},
    )


def _strings(*names):
    return {name: types.Type.STRING for name in names}


RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["incident_header", "resources_assigned", "work_assignments"],
    properties={
        "incident_header": _obj(_strings(
            "incident_name", "operational_period", "date_from", "date_to", "branch", "division_group")),
        "operations_personnel": _obj(_strings(
            "div_group_supervisor", "branch_director", "air_attack_supervisor", "operations_chief")),
        "resources_assigned": types.Schema(
            type=types.Type.ARRAY,
            items=_obj({**_strings("designator", "lwd", "leader", "drop_off", "pick_up"),
                        "num_persons": types.Type.INTEGER}),
        ),
        "work_assignments": _obj(_strings("task", "purpose", "end_state")),
        "special_instructions": types.Schema(type=types.Type.STRING),
        "communications_plan": types.Schema(
            type=types.Type.ARRAY,
            items=_obj(_strings("function", "channel", "rx_frequency", "rx_tone",
                                "tx_frequency", "tx_tone", "mode")),
        ),
        "approval": _obj(_strings("prepared_by", "approved_by", "date", "time")),
    },
)


def extract_form(client: genai.Client, data: bytes, mime_type: str) -> dict:
    """Send one form to Gemini and return the parsed JSON. Raises on API errors."""
    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=[
            types.Part.from_text(text=PROMPT),
            types.Part.from_bytes(data=data, mime_type=mime_type),
        ])],
        config=types.GenerateContentConfig(
            top_p=0.1,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    return json.loads(response.text)


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
    })

    rows = []
    for res in data.get("resources_assigned") or []:
        num = res.get("num_persons") or 0
        rows.append({**base,
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
        rows.append({**base,
                     "comm_function": comm.get("function", ""),
                     "comm_channel": comm.get("channel", ""),
                     "comm_rx_frequency": comm.get("rx_frequency", ""),
                     "comm_rx_tone": comm.get("rx_tone", ""),
                     "comm_tx_frequency": comm.get("tx_frequency", ""),
                     "comm_tx_tone": comm.get("tx_tone", ""),
                     "comm_mode": comm.get("mode", ""),
                     "status": "COMMUNICATION"})
    return rows
