from __future__ import annotations

from typing import Any


SEVERE_TOKENS = (
    "broken",
    "crack",
    "cracked",
    "flat tire",
    "hazard",
    "leak",
    "major dent",
    "shattered",
    "severe",
)
AMBIGUOUS_DAMAGE_TOKENS = (
    "dent",
    "damaged",
    "damage",
    "door ding",
    "mirror",
    "panel",
    "scrape",
)
MINOR_DAMAGE_TOKENS = (
    "dirty",
    "dust",
    "light scratch",
    "scratch",
    "scuff",
    "stain",
)
CLEAR_TOKENS = (
    "all good",
    "clean",
    "looks clean",
    "no damage",
    "no visible damage",
    "nothing found",
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def assess_damage(notes: str, filenames: list[str] | None = None, mode: str = "mock") -> dict[str, Any]:
    normalized_notes = _normalize(notes)

    # The current project runs in mock mode; uploaded filenames are evidence metadata only.
    # Do not infer damage severity from the filename because that creates false positives.
    if any(token in normalized_notes for token in SEVERE_TOKENS):
        return {"severity": "SEVERE", "confidence": 0.92, "detectedDamage": ["major exterior damage"]}
    if any(token in normalized_notes for token in CLEAR_TOKENS):
        return {"severity": "MINOR", "confidence": 0.98, "detectedDamage": ["no visible exterior damage"]}
    if any(token in normalized_notes for token in MINOR_DAMAGE_TOKENS):
        return {"severity": "MINOR", "confidence": 0.87, "detectedDamage": ["surface issue"]}
    if any(token in normalized_notes for token in AMBIGUOUS_DAMAGE_TOKENS):
        return {"severity": "MODERATE", "confidence": 0.61, "detectedDamage": ["possible body damage"]}
    if normalized_notes:
        return {"severity": "MODERATE", "confidence": 0.55, "detectedDamage": ["requires manual review"]}
    return {"severity": "MODERATE", "confidence": 0.51, "detectedDamage": ["insufficient inspection detail"]}

