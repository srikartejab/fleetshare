from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

try:
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover - optional dependency for local mock testing
    AzureOpenAI = None

logger = logging.getLogger("fleetshare.ai")

# Mock fallback tokens
SEVERE_TOKENS = ("broken", "crack", "cracked", "flat tire", "hazard", "leak", "major dent", "shattered", "severe")
AMBIGUOUS_DAMAGE_TOKENS = ("dent", "damaged", "damage", "door ding", "mirror", "panel", "scrape")
MINOR_DAMAGE_TOKENS = ("dirty", "dust", "light scratch", "scratch", "scuff", "stain")
CLEAR_TOKENS = (
    "all good",
    "clean",
    "looks clean",
    "good condition",
    "in good condition",
    "returned in good condition",
    "looks good",
    "no damage",
    "no visible damage",
    "nothing found",
)
TEXT_ONLY_BLOCK_TOKENS = ("damage", "damaged")
MANUAL_REVIEW_REASON = "manual review required; AI assessment unavailable"
MISSING_IMAGE_REASON = "manual review required; image evidence missing"


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _no_damage_assessment(confidence: float) -> dict[str, Any]:
    return {"severity": "NO_DAMAGE", "confidence": confidence, "detectedDamage": ["no visible exterior damage"]}


def _normalize_assessment(raw: dict[str, Any], notes: str) -> dict[str, Any]:
    severity = str(raw.get("severity", "MODERATE")).upper()
    confidence = float(raw.get("confidence", 0.55))
    detected_damage = [str(item) for item in raw.get("detectedDamage", [])]
    detected_text = " ".join(detected_damage).lower()
    normalized_notes = _normalize(notes)
    no_damage_detected = any(token in normalized_notes for token in CLEAR_TOKENS) or any(
        token in detected_text for token in ("no visible exterior damage", "no visible damage", "no damage")
    )

    if severity in {"NO_DAMAGE", "NONE", "CLEAR"} or (severity == "MINOR" and no_damage_detected):
        return _no_damage_assessment(confidence if confidence > 0 else 0.95)
    if severity not in {"MINOR", "MODERATE", "SEVERE"}:
        severity = "MODERATE"
    return {
        "severity": severity,
        "confidence": confidence,
        "detectedDamage": detected_damage,
    }


def _mock_assessment_from_text(notes: str, *, text_only: bool = False) -> dict[str, Any]:
    normalized_notes = _normalize(notes)
    if any(token in normalized_notes for token in SEVERE_TOKENS):
        return {"severity": "SEVERE", "confidence": 0.92, "detectedDamage": ["major exterior damage"]}
    if any(token in normalized_notes for token in CLEAR_TOKENS):
        return _no_damage_assessment(0.98)
    if text_only and any(token in normalized_notes for token in TEXT_ONLY_BLOCK_TOKENS):
        return {"severity": "SEVERE", "confidence": 0.9, "detectedDamage": ["major exterior damage"]}
    if any(token in normalized_notes for token in MINOR_DAMAGE_TOKENS):
        return {"severity": "MINOR", "confidence": 0.87, "detectedDamage": ["surface issue"]}
    if any(token in normalized_notes for token in AMBIGUOUS_DAMAGE_TOKENS):
        return {"severity": "MODERATE", "confidence": 0.61, "detectedDamage": ["possible body damage"]}
    if normalized_notes:
        return {"severity": "MODERATE", "confidence": 0.55, "detectedDamage": ["requires manual review"]}
    return {"severity": "MODERATE", "confidence": 0.51, "detectedDamage": ["insufficient inspection detail"]}


def _manual_review_assessment(reason: str = MANUAL_REVIEW_REASON) -> dict[str, Any]:
    return {
        "severity": "MODERATE",
        "confidence": 0.2,
        "detectedDamage": [reason],
    }


def _azure_openai_config() -> tuple[dict[str, str], list[str]]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_KEY", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
    missing = []
    if not endpoint:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not api_key:
        missing.append("AZURE_OPENAI_KEY")
    if not deployment:
        missing.append("AZURE_OPENAI_DEPLOYMENT")
    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "deployment": deployment,
    }, missing


def _assess_damage_with_azure(notes: str, image_bytes_list: list[bytes] | None) -> dict[str, Any]:
    if not image_bytes_list:
        logger.info("Azure AI inspection requested without image evidence; falling back to text heuristic")
        return _normalize_assessment(_mock_assessment_from_text(notes, text_only=True), notes)

    config, missing = _azure_openai_config()
    if AzureOpenAI is None:
        logger.warning("Azure OpenAI SDK is unavailable; forcing manual review")
        return _manual_review_assessment()
    if missing:
        logger.warning("Azure OpenAI config is incomplete; forcing manual review", extra={"missing": ",".join(missing)})
        return _manual_review_assessment()

    try:
        logger.info("Analyzing damage with Azure OpenAI", extra={"deployment": config["deployment"]})
        client = AzureOpenAI(
            api_key=config["api_key"],
            api_version="2024-02-15-preview",
            azure_endpoint=config["endpoint"],
        )

        base64_image = base64.b64encode(image_bytes_list[0]).decode("utf-8")
        prompt = """
        You are an expert car damage assessor. Analyze the image and return a JSON object with two keys:
        1. "severity": Must be exactly one of the following:
           - "NO_DAMAGE": Car looks clean, normal, or has no visible exterior damage.
           - "SEVERE": Crushed body panels, bent or misaligned parts (like trunk lids or doors), broken light housings, shattered glass, deployed airbags, or major crashes.
           - "MODERATE": Medium dents, deep scratches, scraped bumpers, or missing small non-critical parts.
           - "MINOR": Small surface dents, light scratches, scuffs, or dirt.
        2. "detectedDamage": A list of short strings describing the damage (e.g., ["crushed rear bumper", "smashed windshield"]). If no damage, return ["no visible exterior damage"].
        Return ONLY valid JSON format.
        """

        response = client.chat.completions.create(
            model=config["deployment"],
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        )

        result_json = json.loads(response.choices[0].message.content)
        logger.info("Azure OpenAI damage assessment completed")
        return _normalize_assessment(
            {
                "severity": result_json.get("severity", "MODERATE"),
                "confidence": 0.95,
                "detectedDamage": result_json.get("detectedDamage", []),
            },
            notes,
        )
    except Exception:
        logger.exception("Azure OpenAI damage assessment failed; forcing manual review")
        return _manual_review_assessment()


def assess_damage(notes: str, image_bytes_list: list[bytes] | None = None, mode: str = "mock") -> dict[str, Any]:
    logger.info(
        "Damage assessment requested",
        extra={"mode": mode, "has_images": bool(image_bytes_list), "has_notes": bool(notes.strip())},
    )

    if mode == "azure":
        return _assess_damage_with_azure(notes, image_bytes_list)

    if not image_bytes_list:
        logger.info("Using text-only mock damage assessment")
        return _normalize_assessment(_mock_assessment_from_text(notes, text_only=True), notes)

    logger.info("Using image-backed mock damage assessment")
    return _normalize_assessment(_mock_assessment_from_text(notes), notes)
