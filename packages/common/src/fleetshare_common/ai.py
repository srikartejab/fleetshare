from __future__ import annotations
import os
import json
import base64
from typing import Any

try:
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover - optional dependency for local mock testing
    AzureOpenAI = None

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

def assess_damage(notes: str, image_bytes_list: list[bytes] | None = None, mode: str = "mock") -> dict[str, Any]:
    print(f"--- AI START: Mode is set to '{mode}' ---", flush=True)

    if mode == "azure" and image_bytes_list and AzureOpenAI is not None:
        try:
            print("--- ANALYZING WITH GPT-4o-MINI ---", flush=True)
            client = AzureOpenAI(
                api_key= os.environ.get("AZURE_OPENAI_KEY"),
                api_version="2024-02-15-preview",
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
            )
            deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

            # Convert the raw image bytes to base64 for the prompt
            base64_image = base64.b64encode(image_bytes_list[0]).decode('utf-8')

            # The exact prompt instructing the AI
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
                model=deployment_name,
                response_format={ "type": "json_object" },
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ]
            )

            # Parse the JSON response from GPT
            result_json = json.loads(response.choices[0].message.content)
            print(f"GPT Output: {result_json}", flush=True)

            return _normalize_assessment(
                {
                    "severity": result_json.get("severity", "MODERATE"),
                    "confidence": 0.95,
                    "detectedDamage": result_json.get("detectedDamage", []),
                },
                notes,
            )

        except Exception as e:
            print(f"Azure OpenAI Error: {e}", flush=True)
    elif mode == "azure" and image_bytes_list and AzureOpenAI is None:
        print("--- AZURE OPENAI SDK NOT INSTALLED; USING MOCK ---", flush=True)

    if not image_bytes_list:
        print("--- USING TEXT-ONLY MOCK FOR TESTING ---", flush=True)
        return _normalize_assessment(_mock_assessment_from_text(notes, text_only=True), notes)

    print("--- FALLING BACK TO TEXT MOCK ---", flush=True)
    return _normalize_assessment(_mock_assessment_from_text(notes), notes)
