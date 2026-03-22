from __future__ import annotations
import os
from typing import Any
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

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


def assess_damage(notes: str, image_bytes_list: list[bytes] | None = None, mode: str = "mock") -> dict[str, Any]:
    if mode == "azure" and image_bytes_list:
        try:
            endpoint = os.environ.get("AZURE_VISION_ENDPOINT")
            key = os.environ.get("AZURE_VISION_KEY")
            client = ImageAnalysisClient(endpoint, AzureKeyCredential(key))
            
            all_detected_issues = []
            highest_confidence = 0.0
            
            for image_data in image_bytes_list:
                # Ask Azure for both TAGS and a CAPTION
                result = client.analyze(
                    image_data=image_data,
                    visual_features=[VisualFeatures.TAGS, VisualFeatures.CAPTION]
                )
                
                # 1. Check the Tags (just in case)
                if result.tags is not None:
                    for tag in result.tags.list:
                        if tag.name.lower() in ['damage', 'dent', 'scratch', 'broken', 'crack', 'smashed', 'crash', 'accident']:
                            all_detected_issues.append(tag.name.lower())
                            highest_confidence = max(highest_confidence, tag.confidence)
                            
                # 2. Check the Caption (The secret weapon!)
                if result.caption is not None:
                    caption_text = result.caption.text.lower()
                    print(f"Azure Caption: '{caption_text}'", flush=True)
                    
                    damage_words = ['damage', 'dent', 'scratch', 'broken', 'crack', 'smashed', 'crash', 'wreck', 'shattered']
                    for word in damage_words:
                        if word in caption_text:
                            all_detected_issues.append(word)
                            # Captions use a different confidence scale, so we default to a high one if it explicitly says the word
                            highest_confidence = max(highest_confidence, result.caption.confidence)

            if "broken" in all_detected_issues or "smashed" in all_detected_issues or "crash" in all_detected_issues or "wreck" in all_detected_issues or "shattered" in all_detected_issues:
                return {"severity": "SEVERE", "confidence": highest_confidence, "detectedDamage": list(set(all_detected_issues))}
            elif all_detected_issues:
                return {"severity": "MODERATE", "confidence": highest_confidence, "detectedDamage": list(set(all_detected_issues))}
            else:
                return {"severity": "MINOR", "confidence": 0.95, "detectedDamage": ["no visible exterior damage"]}
                
        except Exception as e:
            print(f"Azure Vision Error: {e}", flush=True)


    print("--- FALLING BACK TO TEXT MOCK ---", flush=True)
    # ... Rest of text mock logic ...

    # --- MOCK TEXT-ONLY LOGIC ---
    normalized_notes = _normalize(notes)
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