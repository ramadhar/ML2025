#!/usr/bin/env python3
"""
Samsung Device Issue Classifier (rule-based)

Classifies an issue into categories using the provided title and contents.
Initial categories:
- Crash Issue
- Camera Issue
- Bluetooth Issue
- NFC Issue
- Notification Issue
- UI Issue
- Other

Usage:
  python main.py --title "amazon shopping app crashed" --content "when searching a product using camera search feature..."

Optional:
  --top-k 2        # return top 2 categories (default 1)
  --explain        # print matched keywords and scores

Notes:
- Rule-based and deterministic, designed to be extended.
- Focused on Samsung device issue descriptions from testers/customers.
"""
from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Categories
CRASH = "Crash Issue"
CAMERA = "Camera Issue"
BLUETOOTH = "Bluetooth Issue"
NFC = "NFC Issue"
NOTIF = "Notification Issue"
UI = "UI Issue"
OTHER = "Other"

ALL_CATEGORIES = [CRASH, CAMERA, BLUETOOTH, NFC, NOTIF, UI]

# Keyword rules (lowercase); each match adds to the score
KEYWORDS: Dict[str, List[str]] = {
    CRASH: [
        # common user-facing crash phrases
        "crash", "crashes", "crashed", "crashing",
        "stopped working", "keeps stopping", "has stopped", "stops working",
        "force close", "force-close", "force stop", "force-stop",
        "stopped responding", "unfortunately", "app stopped", "app has stopped",
        # technical crash hints
        "anr", "application not responding", "fatal exception", "fatal signal",
        "sigsegv", "sigabrt", "java.lang.", "nullpointerexception"
    ],
    CAMERA: [
        "camera", "cam", "selfie", "rear camera", "front camera", "photo", "video",
        "record", "capture", "shutter", "focus", "hdr", "portrait", "night mode",
        "pro mode", "qr", "barcode", "scan", "camera search"
    ],
    BLUETOOTH: [
        "bluetooth", "bt", "pair", "pairing", "paired", "connect", "connected", "disconnect",
        "disconnected", "a2dp", "hfp", "ble", "earbuds", "buds", "headset"
    ],
    NFC: [
        "nfc", "tap to pay", "contactless", "samsung pay", "google pay",
        "secure element", "se", "host card emulation", "hce"
    ],
    NOTIF: [
        "notification", "notifications", "push", "badge", "badges", "heads-up", "banner",
        "silent notification", "no notification", "do not disturb", "dnd", "blocked notifications"
    ],
    UI: [
        "ui", "one ui", "screen", "display", "layout", "button", "icon", "gesture",
        "freeze", "frozen", "stuck", "lag", "stutter", "animation", "render", "touch",
        "tap", "scroll", "scrolling", "ui bug", "ui issue"
    ],
}

# Phrase normalizations to boost certain intents
NORMALIZE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(app|application) (keeps )?(crashing|stopping|closing)\b", re.I), "crash"),
    (re.compile(r"\b(stopped|stops) working\b", re.I), "stopped working"),
    (re.compile(r"\bunfortunately[, ]+.* has stopped\b", re.I), "app has stopped"),
]

@dataclass
class Classification:
    primary: str
    secondary: List[str]
    scores: Dict[str, int]
    reasons: Dict[str, List[str]]


def _prep_text(title: str, content: str) -> str:
    t = f"{title}\n{content}".lower()
    # normalize common phrases
    for pat, repl in NORMALIZE_PATTERNS:
        t = pat.sub(repl, t)
    return t


def _is_wordy(s: str) -> bool:
    """Return True if s starts and ends with a word char; suitable for \b boundaries."""
    return bool(s) and s[0].isalnum() and s[-1].isalnum()


def _score_categories(text: str) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    scores: Dict[str, int] = {cat: 0 for cat in ALL_CATEGORIES}
    reasons: Dict[str, List[str]] = {cat: [] for cat in ALL_CATEGORIES}
    for cat, words in KEYWORDS.items():
        for w in words:
            # Use word boundaries when the token begins/ends with word characters;
            # otherwise fall back to plain substring search (escaped) without \b.
            if _is_wordy(w):
                pattern = rf"\b{re.escape(w)}\b"
            else:
                pattern = re.escape(w)
            if re.search(pattern, text):
                # Boost multi-word phrases slightly
                scores[cat] += 2 if " " in w else 1
                reasons[cat].append(w)
    return scores, reasons


def classify_issue(title: str, content: str, top_k: int = 1) -> Classification:
    text = _prep_text(title, content)
    scores, reasons = _score_categories(text)

    # Heuristics: Crash dominates when present
    if scores[CRASH] > 0:
        # find topical secondaries (e.g., camera crash)
        topical = [c for c in (CAMERA, BLUETOOTH, NFC, NOTIF, UI) if scores[c] > 0]
        return Classification(primary=CRASH, secondary=topical[: max(0, top_k - 1)], scores=scores, reasons=reasons)

    # Otherwise choose top categories by score
    ranked = sorted(ALL_CATEGORIES, key=lambda c: (scores[c], c), reverse=True)
    primary = ranked[0] if scores[ranked[0]] > 0 else OTHER
    secondary: List[str] = []
    if top_k > 1:
        for c in ranked[1:]:
            if scores[c] <= 0:
                break
            secondary.append(c)
            if len(secondary) >= (top_k - 1):
                break
    return Classification(primary=primary, secondary=secondary, scores=scores, reasons=reasons)


def main():
    ap = argparse.ArgumentParser(description="Samsung Device Issue Classifier")
    ap.add_argument("--title", required=True, help="Short issue title")
    ap.add_argument("--content", required=True, help="Detailed issue content/description")
    ap.add_argument("--mode", choices=["rules", "llm"], default="rules", help="Classifier mode: rule-based or LLM (default rules)")
    ap.add_argument("--top-k", type=int, default=1, help="Return top-K categories (rules mode only)")
    ap.add_argument("--explain", action="store_true", help="Show scores and matched keywords (rules mode)")
    ap.add_argument("--json", action="store_true", help="Print JSON output")
    # LLM specific
    ap.add_argument("--model", default=None, help="LLM model name (env OPENAI_MODEL used if not provided)")
    ap.add_argument("--dry-run", action="store_true", help="LLM mode: print constructed prompt without calling the API")
    args = ap.parse_args()

    if args.mode == "llm":
        from llm_classifier import classify_with_llm  # local import to avoid hard dep in rules mode
        out = classify_with_llm(args.title, args.content, model=args.model, dry_run=args.dry_run)
        if args.json or args.dry_run:
            print(json.dumps(out, indent=2))
        else:
            if "prompt" in out:
                print(json.dumps(out, indent=2))
            else:
                print(f"Primary: {out.get('primary')}")
                sec = out.get("secondary") or []
                if sec:
                    print(f"Secondary: {', '.join(sec)}")
                subs = out.get("subtypes") or []
                if subs:
                    print(f"Subtypes: {', '.join(subs)}")
        return

    # rules mode
    result = classify_issue(args.title, args.content, top_k=max(1, args.top_k))
    if args.json:
        print(json.dumps({
            "primary": result.primary,
            "secondary": result.secondary,
            "scores": result.scores if args.explain else None,
            "reasons": result.reasons if args.explain else None,
        }, indent=2))
    else:
        print(f"Primary: {result.primary}")
        if result.secondary:
            print(f"Secondary: {', '.join(result.secondary)}")
        if args.explain:
            print("\nScores:")
            for k in ALL_CATEGORIES:
                print(f"  {k:18} : {result.scores[k]}")
            print("\nMatched keywords:")
            for k in ALL_CATEGORIES:
                if result.reasons[k]:
                    print(f"  {k:18} : {', '.join(result.reasons[k])}")


if __name__ == "__main__":
    main()
