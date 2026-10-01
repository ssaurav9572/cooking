from __future__ import annotations

import json
import time
from typing import Any

import httpx

from config import (
    AI_USAGE_ENABLED,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    VISION_ADVANCE_STATES,
    VISION_HOLD_STATES,
    VISION_RESCUE_STATES,
)
from prompts import (
    COOKING_VISION,
    EXPLAIN,
    FOOD_DETECTION,
    INTENT,
    RECIPE_GENERATION,
    SYSTEM,
    TRANSLATE,
)

TASKS = {
    "intent": "cheap_text",
    "recipe_ideas": "cheap_multimodal",
    "recipe_generation": "multimodal",
    "recipe_validation": "cheap_text",
    "image_food_detection": "multimodal",
    "cooking_vision": "multimodal",
    "translation": "cheap_text",
    "conversation": "cheap_text",
    "complex_reasoning": "advanced",
    "explanation": "cheap_text",
    "active_cooking_voice": "realtime",
}

# Voice-first entry points: STT turns mic audio into text; TTS turns engine cues into speech.
# Both run through the same router so provider choice stays a config decision.
STT_TASKS = {"speech_to_text": "realtime"}
TTS_TASKS = {"text_to_speech": "realtime"}

# Published-order-of-magnitude prices used only for ai_usage estimates.
PRICE = {
    "gemini": {"in": 0.30 / 1_000_000, "out": 2.50 / 1_000_000},
    "deepseek": {"in": 0.14 / 1_000_000, "out": 0.28 / 1_000_000},
    "local": {"in": 0, "out": 0},
}


def route(task: str) -> str:
    return TASKS.get(task, "cheap_text")


def generate(task: str, data: dict, user_id: int | None = None) -> dict:
    lane = route(task)
    started = time.time()
    provider, model, payload = _call(lane, task, data)
    duration_ms = int((time.time() - started) * 1000)
    payload["_meta"] = {
        "provider": provider,
        "model": model,
        "task": task,
        "lane": lane,
        "duration_ms": duration_ms,
        "user_id": user_id,
    }
    _record_usage(task, provider, model, data, payload, duration_ms, user_id)
    return payload


def _estimate_cost(provider: str, data_in: int, data_out: int) -> float:
    prices = PRICE.get(provider) or PRICE["local"]
    # No token counts from these endpoints yet; approximate by serialized size / 4 chars per token.
    in_tokens = max(1, data_in // 4)
    out_tokens = max(1, data_out // 4)
    return round(in_tokens * prices["in"] + out_tokens * prices["out"], 6)


def _record_usage(task, provider, model, data, payload, duration_ms, user_id) -> None:
    if not AI_USAGE_ENABLED:
        return
    try:
        from store import store

        size_in = len(json.dumps(data, ensure_ascii=False))
        size_out = len(json.dumps(payload, ensure_ascii=False))
        store.record_usage({
            "user_id": user_id, "provider": provider, "model": model, "task": task,
            "input_tokens": max(1, size_in // 4), "output_tokens": max(1, size_out // 4),
            "duration_ms": duration_ms, "estimated_cost_usd": _estimate_cost(provider, size_in, size_out),
        })
    except Exception:
        # Usage accounting must never break the request path.
        pass


def _call(lane: str, task: str, data: dict) -> tuple[str, str, dict]:
    prompt = _prompt(task, data)
    image_b64 = data.get("image_base64")
    if lane in {"cheap_text", "cheap_multimodal"} and DEEPSEEK_API_KEY and task != "cooking_vision":
        try:
            return "deepseek", DEEPSEEK_MODEL, _deepseek(prompt)
        except Exception:
            pass
    if GEMINI_API_KEY and (lane != "cheap_text" or image_b64):
        try:
            return "gemini", GEMINI_MODEL, _gemini(prompt, image_b64,
                                                   mime=data.get("image_mime", "image/jpeg"))
        except Exception:
            pass
    if DEEPSEEK_API_KEY:
        try:
            return "deepseek", DEEPSEEK_MODEL, _deepseek(prompt)
        except Exception:
            pass
    return "local", "deterministic-fallback", _fallback(task, data)


def _prompt(task: str, data: dict) -> str:
    if task == "intent":
        return INTENT.format(text=data.get("text", ""))
    if task == "recipe_generation":
        return RECIPE_GENERATION.format(
            data=json.dumps(data, ensure_ascii=False),
            ingredients=", ".join(data.get("allowed_ingredients") or []),
        )
    if task == "explanation":
        return EXPLAIN.format(
            profile=json.dumps(data.get("profile") or {}, ensure_ascii=False),
            dish=json.dumps(data.get("dish") or {}, ensure_ascii=False),
        )
    if task == "translation":
        return TRANSLATE.format(
            target=data.get("target_language", "en"),
            source_text=data.get("text", ""),
        )
    if task == "cooking_vision":
        return COOKING_VISION.format(
            instruction=(data.get("instruction") or "")[:400],
            states=", ".join(sorted(VISION_ADVANCE_STATES | VISION_RESCUE_STATES | VISION_HOLD_STATES)),
        )
    if task == "image_food_detection":
        return FOOD_DETECTION.format()
    return json.dumps({"task": task, "data": data}, ensure_ascii=False)


def _gemini(prompt: str, image_b64: str | None = None, mime: str = "image/jpeg") -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    parts: list[dict] = [{"text": prompt}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    r = httpx.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=40)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _parse(text)


def _deepseek(prompt: str) -> dict:
    r = httpx.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=40,
    )
    r.raise_for_status()
    return _parse(r.json()["choices"][0]["message"]["content"])


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _fallback(task: str, data: dict) -> dict:
    if task == "intent":
        return _fallback_intent(data)
    if task == "explanation":
        dish = (data.get("dish") or {}).get("title") or "This dish"
        return {
            "explanation": (
                f"{dish} fits the pantry and household rules already checked by the engine. "
                "It is scored for cuisine diversity against recent Indian meals, not chosen by the model."
            )
        }
    if task == "recipe_generation":
        return {"recipes": [_fallback_recipe(data, i)]}
    if task == "cooking_vision":
        # No model available: never fake a label. The engine keeps the step.
        return {"visual_state": None, "confidence": 0.0,
                "note": "No vision provider configured. Use your own eyes; tap next when ready."}
    if task == "image_food_detection":
        return {"items": [], "note": "No vision provider configured. Add items manually."}
    if task == "translation":
        return {"translated": data.get("text", ""), "target_language": data.get("target_language"),
                "note": "No text provider configured; returned source text unchanged."}
    return {"ok": True, "task": task}


def _fallback_intent(data: dict) -> dict:
    import re

    from i18n import detect_language

    text = (data.get("text") or "").lower()
    catalog = []
    try:
        from store import store

        catalog = [i["canonical_name"] for i in store.ingredients()]
    except Exception:
        catalog = ["chicken", "rice", "tomato", "paneer", "lentil", "onion", "potato", "eggplant", "sattu"]
    ingredients = [name for name in catalog if name.lower() in text]
    people_match = re.search(r"\b(\d{1,2})\s*(?:people|persons|members|log|loag|ka jaldi)?", text)
    people = int(people_match.group(1)) if people_match and 1 <= int(people_match.group(1)) <= 20 else 2
    budget_match = re.search(r"(?:under|below|max|budget)\D{0,6}(\d{2,6})", text)
    return {
        "people": people,
        "budget": float(budget_match.group(1)) if budget_match else None,
        "ingredients": ingredients,
        "novelty": "high" if any(w in text for w in ("never", "new", "something different", "naya")) else "medium",
        "meal": "dinner" if "dinner" in text else ("lunch" if "lunch" in text else "any"),
        "language": detect_language(data.get("text") or "") or "en",
    }


def _fallback_recipe(data: dict, index: int) -> dict:
    """Deterministic 'invention': compose a real recipe from what the user has.

    One-pot grain + protein + vegetable template set. Engines still decide
    nutrition/cost/diet afterwards; this only proposes structure.
    """
    have = [str(x).strip() for x in (data.get("allowed_ingredients") or []) if str(x).strip()]
    if not have:
        have = ["Rice", "Tomato"]
    proteins = [x for x in have if x.lower() in {"chicken", "paneer", "lentil", "dal", "chickpea", "egg", "fish", "sattu"}]
    protein = proteins[0] if proteins else (have[index % len(have)] if have else "Lentil")
    veges = [x for x in have if x != protein] or ["Tomato"]
    carb = next((x for x in have if x.lower() in {"rice", "wheat flour", "atta", "potato"}), "Rice")
    oil = next((x for x in have if "oil" in x.lower()), "Mustard oil")
    title_bits = f"{protein} {['Tadka', 'Masala', 'One-Pot', 'Stir-fry'][index % 4]}".strip()
    return {
        "title": title_bits,
        "servings": int(data.get("people") or 2),
        "difficulty": "easy",
        "time_minutes": 30,
        "cuisine": data.get("cuisine") or "Indian",
        "ingredients": [
            {"name": protein, "quantity": 250, "unit": "g"},
            {"name": carb, "quantity": 200, "unit": "g"},
            {"name": veges[0], "quantity": 150, "unit": "g"},
            {"name": oil, "quantity": 15, "unit": "ml"},
        ],
        "steps": [
            {"step": 1, "instruction": f"Heat the oil, add {veges[0].lower()} and cook until soft.", "duration_seconds": 300},
            {"step": 2, "instruction": f"Add {protein.lower()} and cook until changes color throughout.", "duration_seconds": 480},
            {"step": 3, "instruction": f"Stir in {carb.lower()} and water, cover and simmer until cooked.", "duration_seconds": 900},
        ],
        "confidence": 0.4,
        "generated_by": "deterministic-template",
    }
