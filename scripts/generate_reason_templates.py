"""Build-time script: generate reason templates with Gemini.

Run this once whenever you want to refresh the templates. Output is
committed to the repo as app/data/reason_templates.json.

Usage:
    uv run python scripts/generate_reason_templates.py

Philosophy: this script exists because "AI does the work at build time,
rules do the work at runtime" is cheaper, faster, more testable, and
offline-capable compared to calling Gemini on every request.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make the app package importable when running this script directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.gemini import generate_json  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "app" / "data" / "reason_templates.json"

REASON_CODES = [
    "entry_standard",
    "entry_beat_crush",
    "entry_step_free",
    "entry_weather_covered",
    "exit_standard",
    "exit_pre_peak",
    "exit_after_ceremony",
    "exit_weather_urgent",
]

PROMPT = """You are writing a cricket stadium companion app called FlowPass.
For each reason code below, produce a short, friendly headline template
(max 60 characters) and subtext template (max 120 characters).

Templates may include the placeholder {gate_name} which will be substituted
at runtime. Do not invent other placeholders.

The tone is calm, direct, Indian-English, not overly casual, not corporate.
Imagine a friend who knows the stadium giving you a tip.

Reason codes:
- entry_standard: plenty of time, calm approach
- entry_beat_crush: ingress crush is building, get in now
- entry_step_free: user needs step-free route, reassure them
- entry_weather_covered: rain expected, covered gate chosen
- exit_standard: exit mode active but no urgency yet
- exit_pre_peak: exit flood imminent, leave now to beat metro peak
- exit_after_ceremony: trophy ceremony ending, coordinate leaving
- exit_weather_urgent: rain starting, hurry to covered transit

Return JSON mapping each reason_code to {"headline": "...", "subtext": "..."}.
"""

SCHEMA_HINT = (
    '{ "entry_standard": {"headline": "...", "subtext": "..."}, '
    '"entry_beat_crush": {"headline": "...", "subtext": "..."}, ... }'
)


def main() -> None:
    print(f"Generating reason templates via Gemini -> {OUTPUT_PATH}")
    templates = generate_json(PROMPT, SCHEMA_HINT)

    missing = [code for code in REASON_CODES if code not in templates]
    if missing:
        raise SystemExit(f"Gemini response missing reason codes: {missing}")

    payload = {
        "_generated_at": datetime.now(UTC).isoformat(),
        "_source_prompt_hash": hashlib.sha256(PROMPT.encode()).hexdigest()[:16],
        "_model": "gemini-flash-latest",
        "templates": templates,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(templates)} templates to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
