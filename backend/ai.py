"""AI router. One call site: ai.generate(task, data). Never scatter provider calls."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, GEMINI_API_KEY, GEMINI_MODEL
from prompts import EXPLAIN, INTENT, RECIPE_GENERATION, SYSTEM

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
    payload["_meta"] = {
        "provider": provider,
        "model": model,
        "task": task,
        "lane": lane,
        "duration_ms": int((time.time() - started) * 1000),
        "user_id": user_id,
    }
    return payload


def _call(lane: str, task: str, data: dict) -> tuple[str, str, dict]:
    prompt = _prompt(task, data)
    if lane in {"cheap_text", "cheap_multimodal"} and DEEPSEEK_API_KEY and task != "cooking_vision":
        try:
            return "deepseek", DEEPSEEK_MODEL, _deepseek(prompt)
        except Exception:
            pass
    if GEMINI_API_KEY and lane != "cheap_text":
        try:
            return "gemini", GEMINI_MODEL, _gemini(prompt)
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
    return json.dumps({"task": task, "data": data}, ensure_ascii=False)


def _gemini(prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": [{"text": prompt}]}],
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
        text = (data.get("text") or "").lower()
        ingredients = [w for w in ("chicken", "rice", "tomato", "paneer", "dal") if w in text]
        return {
            "people": 4 if "4" in text else 2,
            "budget": 700 if "700" in text else None,
            "ingredients": ingredients,
            "novelty": "high" if "never" in text or "new" in text else "medium",
            "meal": "dinner",
        }
    if task == "explanation":
        dish = (data.get("dish") or {}).get("title") or "This dish"
        return {
            "explanation": (
                f"{dish} fits the pantry and household rules already checked by the engine. "
                "It is scored for cuisine diversity against recent Indian meals, not chosen by the model."
            )
        }
    return {"ok": True, "task": task}
