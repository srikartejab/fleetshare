from __future__ import annotations

from typing import Any


def assess_damage(notes: str, filenames: list[str]) -> dict[str, Any]:
    text = f"{notes} {' '.join(filenames)}".lower()
    if any(token in text for token in ("dent", "crack", "severe", "broken", "flat", "hazard")):
        return {"severity": "SEVERE", "confidence": 0.92, "detectedDamage": ["major body damage"]}
    if any(token in text for token in ("scratch", "dirty", "cleanliness", "light")):
        return {"severity": "MINOR", "confidence": 0.87, "detectedDamage": ["surface issue"]}
    return {"severity": "MODERATE", "confidence": 0.61, "detectedDamage": ["requires manual review"]}

