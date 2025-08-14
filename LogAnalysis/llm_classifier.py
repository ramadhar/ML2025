"""
LLM-based issue classifier for Samsung device issues.

- Builds a concise prompt listing allowed issue types and their meanings.
- Injects the provided title and content.
- Calls an LLM (OpenAI) to return a JSON classification.

Environment:
- OPENAI_API_KEY (required to actually call OpenAI)
- OPENAI_MODEL (optional, default: gpt-4o-mini)
"""
from __future__ import annotations
import json
import os
from typing import Dict, List, Tuple, Any

ISSUE_TYPES: List[Tuple[str, str]] = [
    ("App Crash", "Problem is a crash in an app (force close, 'stopped working', fatal exception, SIGSEGV/SIGABRT)."),
    ("App ANR", "Problem is 'Application Not Responding' (ANR): app freezes or becomes unresponsive."),
    ("Camera Issue", "Problem related to camera usage: capture, record, focus, modes, QR/scan, camera search."),
    ("Bluetooth Issue", "Problem related to Bluetooth: pairing, connection stability, audio profiles, earbuds/headsets."),
    ("NFC Issue", "Problem with NFC or contactless payments (Samsung Pay/Google Pay, HCE, secure element)."),
    ("Notification Issue", "Problem with notifications: missing, delayed, badges, heads-up banners, DND/blocked."),
    ("UI Issue", "User interface/experience problem: layout, rendering, freezing UI, gestures, animations, touch/scroll."),
    ("Other", "Doesn’t cleanly fit above categories."),
]

SYSTEM_INSTRUCTION = (
    "You are a Samsung device issue triage assistant. Classify the user-reported issue into predefined categories. "
    "Read the title and content. Decide the primary category and optional secondary categories if clearly implicated. "
    "Use only the allowed labels provided. Be conservative; if uncertain, pick 'Other'. Return strict JSON only."
)

JSON_SCHEMA_NOTE = (
    "Output JSON with keys: primary (string), secondary (array of strings). "
    "Use only allowed labels exactly as provided. No extra fields, no prose."
)


def build_prompt(title: str, content: str) -> Dict[str, Any]:
    labels = "\n".join([f"- {name}: {desc}" for name, desc in ISSUE_TYPES])
    user_block = (
        f"Allowed labels and meanings:\n{labels}\n\n"
        f"Title:\n{title}\n\n"
        f"Content:\n{content}\n\n"
        f"{JSON_SCHEMA_NOTE}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_block},
    ]
    return {"messages": messages}


def call_openai(messages: List[Dict[str, str]], model: str | None = None, temperature: float = 0.0) -> Dict[str, Any]:
    """Call OpenAI Chat Completions API and return parsed JSON dict.
    Requires `openai` python package and OPENAI_API_KEY env.
    """
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot call OpenAI. Use --dry-run to inspect prompt.")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("openai package not installed. Run: pip install openai") from e

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON substring
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise RuntimeError(f"Model did not return valid JSON: {text}")

    # Validate keys
    primary = data.get("primary")
    secondary = data.get("secondary", [])
    allowed = {name for name, _ in ISSUE_TYPES}
    if primary not in allowed:
        # Fallback to Other if needed
        primary = "Other"
    sec = [s for s in secondary if s in allowed and s != primary]
    return {"primary": primary, "secondary": sec}


def classify_with_llm(title: str, content: str, model: str | None = None, dry_run: bool = False) -> Dict[str, Any]:
    prompt = build_prompt(title, content)
    if dry_run:
        # Return the prompt for inspection without making an API call
        return {"prompt": prompt}
    return call_openai(prompt["messages"], model=model)
