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
    ("Audio Issue", "Problem with audio playback/record/voice: noise, wrong path, volume, dual playback, routing."),
    ("Wi-Fi Issue", "Problem with Wi‑Fi connectivity: cannot connect, drops, poor throughput, captive portal, DHCP/DNS."),
    ("Mobile Network Issue", "Problem with cellular/IMS: no service, data, VoLTE/VoNR/5G attach, calls, SMS/MMS/RCS."),
    ("Battery/Thermal Issue", "Abnormal drain or heating/thermal throttling."),
    ("Charging/USB Issue", "Problem charging, cable/USB/PD, file transfer (MTP/PTP), OTG."),
    ("Display/Touch Issue", "Screen brightness/color, flicker, ghost touches, dead zones, refresh rate."),
    ("Sensor/GPS Issue", "Problem with sensors, motion, compass, or location accuracy (GPS/GNSS)."),
    ("Storage/FS Issue", "Insufficient storage, filesystem errors, SD card issues."),
    ("Media Playback Issue", "Video/audio playback problems not specific to Bluetooth."),
    ("System Update/OTA Issue", "Update failures, regressions after OTA, rollback needed."),
    ("Security/Knox Issue", "Problems with Knox features, device admin, or security prompts."),
    ("Samsung Pay Issue", "Problems making payments, provisioning cards, or region errors."),
    ("DeX Issue", "Samsung DeX problems: external display, UI, input devices."),
    ("Bixby Issue", "Bixby or voice assistant malfunctions."),
    ("Accessibility Issue", "Screen readers, magnification, captions, accessibility shortcuts."),
    ("Performance Issue", "Lag, stutter, slow performance unrelated to ANR/crash."),
    ("App Install/Store Issue", "Galaxy Store/Play Store install/update failures."),
    ("Permissions Issue", "Permission prompts, denied access blocking features."),
    ("Clock/Alarm Issue", "Alarms not ringing, time sync issues."),
    ("Contacts/Phone Issue", "Call logs, contacts, dialer behaviors."),
    ("Messaging Issue", "SMS/MMS/RCS send/receive problems."),
    ("Email Issue", "Email sync or send/receive problems."),
    ("File Share/Quick Share Issue", "Quick Share/Bluetooth share/Nearby Share problems."),
    ("Hotspot/Tethering Issue", "Mobile hotspot or USB tethering not working."),
    ("VPN Issue", "VPN cannot connect or breaks connectivity."),
    ("Enterprise/MDM Issue", "Work profile or MDM policy related issues."),
    ("Localization/Language Issue", "Incorrect language/locale/formatting."),
    ("Backup/Restore Issue", "Smart Switch/backup/restore problems."),
    ("Keyboard/IME Issue", "Typing, autocorrect, IME switching issues."),
    ("Launcher/Home/Widget Issue", "Home screen, app drawer, widget issues."),
    ("Lockscreen/Biometric Issue", "Fingerprint/face unlock or lockscreen anomalies."),
    ("Wallpaper/Themes Issue", "Themes, wallpapers, appearance glitches."),
    ("Other", "Doesn’t cleanly fit above categories."),
]

# Optional subtypes catalog for selected categories (e.g., Audio)
SUBTYPES: Dict[str, List[Tuple[str, str]]] = {
    "Audio Issue": [
        ("Noise in audio", "Unwanted noise/distortion/hiss/crackle during playback/recording/calls."),
        ("Dual audio playing", "Two audio streams audible at once (e.g., ringtone + media)."),
        ("Wrong audio path", "Audio routed to receiver/speaker/Bluetooth incorrectly."),
        ("Low volume", "Volume intensity is too low despite settings."),
        ("Volume auto decreased", "Volume reduces automatically without user action."),
        ("Audio delay/latency", "Noticeable delay between action and sound output."),
        ("Audio stutter", "Intermittent stutter/choppy audio."),
        ("No audio", "No sound output where expected."),
    ],
    "Camera Issue": [
        ("Focus failure", "Cannot focus or focus hunts."),
        ("Capture failure", "Shutter fails or save fails."),
        ("Preview freeze", "Viewfinder freezes or is black."),
        ("Mode crash", "Crash when using specific mode (e.g., portrait, night)."),
    ],
    "Bluetooth Issue": [
        ("Pairing failure", "Cannot pair or pairing loops."),
        ("Frequent disconnect", "Device disconnects intermittently."),
        ("Audio stutter/quality", "Poor quality or stutter over A2DP."),
        ("Mic/Call routing", "Wrong path during calls (HFP)."),
    ],
    "Notification Issue": [
        ("Missing notifications", "No notification received."),
        ("Delayed notifications", "Noticeably delayed notifications."),
        ("Badge missing", "App icon badges not updating."),
        ("DND blocking", "Do Not Disturb causing suppression."),
    ],
}

SYSTEM_INSTRUCTION = (
    "You are a Samsung device issue triage assistant. Classify the user-reported issue into predefined categories. "
    "Read the title and content. Decide the primary category and optional secondary categories if clearly implicated. "
    "Use only the allowed labels provided. Be conservative; if uncertain, pick 'Other'. Return strict JSON only."
)

JSON_SCHEMA_NOTE = (
    "Output JSON with keys: primary (string), secondary (array of strings), subtypes (array of strings, optional). "
    "Pick subtypes only from the allowed list for the chosen primary (if provided). "
    "Use only allowed labels exactly as provided. No extra fields, no prose."
)


def build_prompt(title: str, content: str) -> Dict[str, Any]:
    labels = "\n".join([f"- {name}: {desc}" for name, desc in ISSUE_TYPES])
    # If subtypes exist for a label, include them
    subtype_blocks: List[str] = []
    for label, items in SUBTYPES.items():
        lines = "\n".join([f"  * {st}: {sd}" for st, sd in items])
        subtype_blocks.append(f"Subtypes for {label}:\n{lines}")
    subtype_text = ("\n\n" + "\n\n".join(subtype_blocks)) if subtype_blocks else ""
    user_block = (
        f"Allowed labels and meanings:\n{labels}{subtype_text}\n\n"
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
    # Validate subtypes for chosen primary (if any
    raw_sub = data.get("subtypes", []) or []
    allowed_subs = {st for st, _ in SUBTYPES.get(primary, [])}
    subs = [s for s in raw_sub if s in allowed_subs]
    return {"primary": primary, "secondary": sec, "subtypes": subs}


def classify_with_llm(title: str, content: str, model: str | None = None, dry_run: bool = False) -> Dict[str, Any]:
    prompt = build_prompt(title, content)
    if dry_run:
        # Return the prompt for inspection without making an API call
        return {"prompt": prompt}
    return call_openai(prompt["messages"], model=model)
