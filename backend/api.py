from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

import ai
import i18n
from auth import AuthError, token_issue, token_user_id
from commerce import commerce
from config import AUTH_MODE, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, VISION_MIN_CONFIDENCE
from decision import import_policy, judge_recipe_import
from engine import (
    BudgetEngine,
    CookingEngine,
    DietEngine,
    FoodHistoryEngine,
    NutritionEngine,
    PantryEngine,
    RecipeEngine,
    RecommendationEngine,
)
from recipe_import import parse_recipe_text, recipe_from_review
from store import store

router = APIRouter(prefix="/api")

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def user_id(x_user_id: int | None) -> int:
    return x_user_id or 1


def _resolve_uid(x_user_id: int | None, authorization: str | None = None) -> int:
    try:
        uid = token_user_id(authorization)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return uid or user_id(x_user_id)


def household_constraints(uid: int) -> list[dict]:
    # Household membership drives hard diet filters. Slice keeps household 1 semantics.
    return store.household_members(1)


def _recipe_payload(recipe: dict, budget: float | None, people: int, uid: int) -> dict:
    attached = RecipeEngine.attach(recipe, store.ingredients())
    attached["servings"] = people
    diet = DietEngine.validate(attached, household_constraints(1))
    nutrition = NutritionEngine.calculate(attached, people)
    cost = BudgetEngine.validate(attached, budget)
    pantry = PantryEngine.missing(attached, store.pantry(uid))
    fit = 1 - (len(pantry["missing"]) / max(len(attached["ingredients"]), 1))
    scored = RecommendationEngine.score(attached, store.profile(uid), fit, cost["ok"], diet["ok"])
    return {
        "id": attached.get("id"),
        "title": attached.get("canonical_name") or attached.get("title"),
        "cuisine": attached.get("cuisine"),
        "region": attached.get("region"),
        "country": attached.get("country"),
        "difficulty": attached.get("difficulty"),
        "source_type": attached.get("source_type", "canonical"),
        "time_minutes": (attached.get("prep_minutes") or 0) + (attached.get("cook_minutes") or 0),
        "ingredients": attached["ingredients"],
        "steps": attached.get("steps") or [],
        "diet": diet,
        "nutrition": nutrition,
        "estimated_cost": cost,
        "pantry": pantry,
        "score": scored,
    }


@router.get("/config")
def client_config():
    """Everything the mobile client needs to stay dynamic — no hardcoded lists in JS."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "default_language": DEFAULT_LANGUAGE,
        "auth_mode": AUTH_MODE,
        "vision_min_confidence": VISION_MIN_CONFIDENCE,
        "store": store.kind,
    }


@router.post("/auth/login")
def login(body: dict):
    """Dev mode echoes an X-User-Id style session; jwt mode issues a signed token."""
    uid = int(body.get("user_id") or 1)
    if AUTH_MODE == "jwt":
        email = (body.get("email") or "").strip()
        if not email:
            raise HTTPException(422, "email required")
        known = store.user(uid)
        if not known or known.get("email") != email:
            raise HTTPException(401, "unknown user")
        return {"token": token_issue(uid), "user_id": uid}
    return {"user_id": uid, "mode": "header"}


@router.get("/i18n/{language}")
def strings(language: str):
    lang = i18n.normalize_language(language)
    return {"language": lang, "strings": {key: i18n.t(key, language=lang)
                                          for key in ("cue.timer_started", "cue.looks_ready",
                                                      "cue.keep_going", "cue.rescue", "cue.done",
                                                      "app.tagline")}}


@router.post("/translate")
def translate(body: dict, x_user_id: int | None = Header(default=None)):
    text = body.get("text") or ""
    target = i18n.normalize_language(body.get("target_language"))
    result = ai.generate("translation", {"text": text, "target_language": target}, user_id(x_user_id))
    return {"translated": result.get("translated", text), "target_language": target, "meta": result.get("_meta")}


@router.post("/chat")
def chat(body: dict, x_user_id: int | None = Header(default=None), authorization: str | None = Header(default=None)):
    uid = _resolve_uid(x_user_id, authorization)
    intent = ai.generate("intent", {"text": body.get("message", "")}, uid)
    return {"intent": intent, "next": "POST /api/recipe/generate"}


@router.post("/recipe/generate")
def generate(body: dict, x_user_id: int | None = Header(default=None),
             authorization: str | None = Header(default=None)):
    """Score existing matches AND invent new dishes from what the user says they have."""
    uid = _resolve_uid(x_user_id, authorization)
    text = body.get("message") or ""
    intent = body.get("intent") or ai.generate("intent", {"text": text}, uid)
    people = int(body.get("people") or intent.get("people") or 2)
    budget = body.get("budget", intent.get("budget"))
    if budget is not None:
        budget = float(budget)
    have = {p["name"].lower() for p in store.pantry(uid)}
    for name in intent.get("ingredients") or []:
        have.add(name.lower())

    cards = []
    for recipe in store.recipes(uid):
        card = _recipe_payload(recipe, budget, people, uid)
        names = {i["name"].lower() for i in card["ingredients"]}
        if have and not (names & have) and body.get("require_pantry"):
            continue
        if not card["diet"]["ok"]:
            continue
        cards.append(card)

    # Invention path: ask the router for novel dishes from the stated ingredients.
    if body.get("generate", True):
        generated = ai.generate(
            "recipe_generation",
            {
                "request": text,
                "allowed_ingredients": sorted(have),
                "people": people,
                "cuisine": body.get("cuisine"),
                "household_diet": [m.get("diet_profile") for m in household_constraints(1)],
            },
            uid,
        )
        for proposal in generated.get("recipes") or []:
            try:
                normalized = _normalize_generated(proposal, have)
            except ValueError:
                continue
            card = _recipe_payload(normalized, budget, people, uid)
            card["generated"] = True
            card["generation_meta"] = generated.get("_meta")
            if not card["diet"]["ok"]:
                continue
            cards.append(card)

    cards.sort(key=lambda c: c["score"]["score"], reverse=True)
    top = cards[:3]
    profile = store.profile(uid)
    for card in top:
        card["explanation"] = ai.generate(
            "explanation",
            {"profile": profile, "dish": {"title": card["title"], "cuisine": card["cuisine"]}},
            uid,
        ).get("explanation")
    return {
        "intent": intent,
        "candidates": top,
        "note": "Scores and nutrition are deterministic. Generated dishes are proposals validated by the engines.",
    }


def _normalize_generated(proposal: dict, have: set[str]) -> dict:
    """Turn an AI recipe proposal into the canonical shape, then let engines vet it."""
    title = str(proposal.get("title") or "").strip()
    if not title:
        raise ValueError("generated recipe has no title")
    catalog = {i["canonical_name"].lower(): i["canonical_name"] for i in store.ingredients()}
    ingredients = []
    for item in (proposal.get("ingredients") or [])[:40]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        canonical = catalog.get(name.lower(), name)
        quantity = item.get("quantity")
        ingredients.append({
            "name": canonical,
            "quantity": float(quantity) if isinstance(quantity, (int, float)) else None,
            "unit": str(item.get("unit") or "g"),
        })
    steps = []
    for i, step in enumerate(proposal.get("steps") or []):
        instruction = str(step.get("instruction") or "").strip()
        if not instruction:
            continue
        duration = step.get("duration_seconds")
        steps.append({"step": i + 1, "instruction": instruction,
                      "duration_seconds": int(duration) if isinstance(duration, (int, float)) else 0})
    if not ingredients or not steps:
        raise ValueError("generated recipe lacks ingredients or steps")
    time_minutes = int(proposal.get("time_minutes") or 30)
    return {
        "canonical_name": title[:200],
        "cuisine": str(proposal.get("cuisine") or "Indian")[:80],
        "region": None, "country": None,
        "difficulty": str(proposal.get("difficulty") or "easy"),
        "servings": int(proposal.get("servings") or 2),
        "prep_minutes": max(0, time_minutes // 3),
        "cook_minutes": max(0, time_minutes - time_minutes // 3),
        "source_type": "ai_generated",
        "confidence": float(proposal.get("confidence") or 0.5),
        "ingredients": ingredients,
        "steps": steps,
    }


def _available_recipes(uid: int) -> list[dict]:
    return store.recipes(uid)


@router.post("/recipes/import/preview")
def recipe_import_preview(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    source = body.get("text")
    if not isinstance(source, str):
        raise HTTPException(422, "recipe text must be a string")
    try:
        recipe, warnings, source_type = parse_recipe_text(source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    judgment = judge_recipe_import(source, recipe)
    policy = import_policy(recipe, judgment)
    preview_id = store.next_preview_id()
    store.remember_import(preview_id, {"user_id": uid, "recipe": recipe, "warnings": warnings, "source_type": source_type})
    return {
        "preview_id": preview_id,
        "recipe": recipe,
        "warnings": warnings,
        "decision": policy,
        "decision_provider": judgment.get("provider", "local"),
        "source_type": source_type,
    }


@router.post("/recipes/import/commit")
def recipe_import_commit(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    preview_id = body.get("preview_id")
    if not isinstance(preview_id, int):
        raise HTTPException(404, "recipe import preview not found")
    pending = store.pending_import(preview_id)
    if not pending or pending["user_id"] != uid:
        raise HTTPException(404, "recipe import preview not found")
    if body.get("confirm_review") is not True:
        raise HTTPException(400, "review and confirm the recipe fields before saving")
    try:
        recipe = recipe_from_review(
            body.get("title", ""),
            body.get("cuisine", ""),
            body.get("ingredients_text", ""),
            body.get("steps_text", ""),
            body.get("servings", 2),
            body.get("prep_minutes", 0),
            body.get("cook_minutes", 0),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    recipe.update({"owner_user_id": uid, "source_type": pending["source_type"], "confidence": 0.8})
    saved = store.insert_recipe(recipe)
    store.forget_import(preview_id)
    note = ("Saved to your private recipe collection."
            if store.kind == "mysql" else "Saved in this running app instance (memory store).")
    return {"recipe": {**recipe, "id": saved["id"]}, "saved": True, "note": note}


@router.post("/recipe/{recipe_id}/start")
def start(recipe_id: int, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    recipe = store.get_recipe(recipe_id)
    if not recipe or recipe.get("owner_user_id") not in (None, uid):
        raise HTTPException(404, "recipe not found")
    language = i18n.normalize_language(store.profile(uid).get("language") or store.user(uid).get("language"))
    session = {
        "user_id": uid,
        "recipe_id": recipe_id,
        "title": recipe["canonical_name"],
        "current_step": 1,
        "status": "active",
        "steps": recipe["steps"],
        "language": language,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "state": {"step": 1},
        "timeline": [{"event": "start", "step": 1, "at": datetime.now(timezone.utc).isoformat()}],
    }
    created = store.create_session(session)
    started = CookingEngine.transition(created, None, "start")
    created.update({k: v for k, v in started.items() if k != "state"})
    created["state"] = started["state"]
    store.update_session(created["id"], {"state": created["state"]})
    return created


@router.get("/cooking/active")
def active_session(x_user_id: int | None = Header(default=None)):
    """Server-side resume: survives app switches and phone calls (no sessionStorage)."""
    uid = user_id(x_user_id)
    session = store.active_session_for_user(uid)
    if not session:
        return {"session": None}
    return {"session": _session_view(session)}


def _session_view(session: dict) -> dict:
    idx = int(session.get("current_step") or 1)
    steps = session.get("steps") or []
    current = steps[idx - 1] if 0 < idx <= len(steps) else {}
    return {
        "id": session["id"],
        "title": session.get("title"),
        "current_step": idx,
        "total_steps": len(steps),
        "status": session.get("status"),
        "instruction": current.get("instruction", ""),
        "timer": CookingEngine.timer_for(session),
        "state": session.get("state") or {},
        "language": session.get("language") or DEFAULT_LANGUAGE,
        "steps": steps,
    }


@router.post("/cooking/{session_id}/message")
def cooking_message(session_id: int, body: dict):
    action = body.get("action")
    if action not in {"next", "prev", "complete"}:
        raise HTTPException(422, "action must be next, prev, or complete")
    session = _session(session_id)
    update = CookingEngine.transition(session, body.get("vision"), action)
    timeline = list(session.get("timeline") or [])
    timeline.append({"event": action, "step": update["current_step"],
                     "at": datetime.now(timezone.utc).isoformat()})
    merged_state = update.pop("state")
    merged_state["timeline_note"] = f"{action}@{update['current_step']}"
    updated = store.update_session(session_id, {**update, "state": merged_state, "timeline": timeline})
    return _session_view(updated)


@router.post("/cooking/{session_id}/vision")
def cooking_vision(session_id: int, body: dict):
    """Real vision loop: frame -> Gemini label -> confidence gate -> engine decides."""
    session = _session(session_id)
    image_b64 = body.get("image_base64")
    idx = int(session.get("current_step") or 1)
    steps = session.get("steps") or []
    instruction = (steps[idx - 1].get("instruction") if 0 < idx <= len(steps) else "") or ""
    if image_b64:
        try:
            raw_len = len(base64.b64decode(image_b64, validate=False))
        except Exception:
            raise HTTPException(422, "image_base64 is not valid base64")
        if raw_len > MAX_IMAGE_BYTES:
            raise HTTPException(413, "frame too large; downscale on device before sending")
        label = ai.generate("cooking_vision",
                            {"image_base64": image_b64, "image_mime": body.get("image_mime", "image/jpeg"),
                             "instruction": instruction},
                            session["user_id"])
    elif body.get("visual_state"):
        # Manual/self-reported label path stays available (and honest about confidence).
        label = {"visual_state": body["visual_state"],
                 "confidence": float(body.get("confidence", 1.0)),
                 "observation": "self-reported"}
    else:
        raise HTTPException(422, "send image_base64 or an explicit visual_state")
    trusted = (label.get("confidence") or 0) >= VISION_MIN_CONFIDENCE
    update = CookingEngine.transition(session, label, "hold")
    timeline = list(session.get("timeline") or [])
    timeline.append({"event": "vision", "state": label.get("visual_state"),
                     "confidence": label.get("confidence"), "trusted": trusted,
                     "at": datetime.now(timezone.utc).isoformat()})
    merged_state = update.pop("state")
    merged_state["last_label"] = {k: label.get(k) for k in ("visual_state", "confidence", "observation")}
    updated = store.update_session(session_id, {**update, "state": merged_state, "timeline": timeline})
    view = _session_view(updated)
    view["vision"] = {"label": label, "trusted": trusted, "meta": label.get("_meta")}
    view["cues"] = update.get("cues") or []
    return view


@router.post("/pantry/scan")
def pantry_scan(body: dict, x_user_id: int | None = Header(default=None)):
    """Fridge/pantry photo -> auto-inventory via the image_food_detection task."""
    uid = user_id(x_user_id)
    image_b64 = body.get("image_base64")
    if not image_b64:
        raise HTTPException(422, "image_base64 is required")
    detection = ai.generate("image_food_detection",
                            {"image_base64": image_b64, "image_mime": body.get("image_mime", "image/jpeg")},
                            uid)
    items = detection.get("items") or []
    added = []
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or float(item.get("confidence") or 0) < VISION_MIN_CONFIDENCE:
            continue
        try:
            added.append(store.add_pantry({"user_id": uid, "name": name,
                                           "quantity": item.get("approx_quantity") or 0,
                                           "unit": item.get("unit") or "pcs"}))
        except ValueError:
            continue  # unknown ingredient: skip rather than poison the pantry
    return {"detected": items, "added": added, "meta": detection.get("_meta")}


@router.post("/meal/log")
def log_meal(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    nutrition = body.get("nutrition") or {}
    per = nutrition.get("per_serving") or {}
    event = {
        "id": None,
        "user_id": uid,
        "event_type": "COOKED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "calories": per.get("calories"),
        "protein_g": per.get("protein_g"),
        "carbs_g": per.get("carbs_g"),
        "fat_g": per.get("fat_g"),
        "amount": (body.get("estimated_cost") or {}).get("amount"),
        "currency": store.user(uid).get("currency") or "INR",
        "data": {
            "dish": body.get("title"),
            "servings": body.get("servings_eaten") or 1,
            "source": "cooked_in_app",
            "recipe_id": body.get("recipe_id"),
            "cuisine": body.get("cuisine"),
        },
    }
    stored = store.log_event(event)
    event["id"] = stored.get("id")
    profile = store.profile(uid)
    recent = list(profile.get("recent_dishes") or [])
    if body.get("title"):
        recent.insert(0, body["title"])
        store.save_profile(uid, {"recent_dishes": recent[:8]})
    return event


@router.get("/food/today")
def today(x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    meals = [e for e in store.events(uid) if e["event_type"] in {"MEAL", "COOKED", "SNACK"}]
    currency = store.user(uid).get("currency") or "INR"
    return {
        "meals": meals,
        "calories": round(sum(e.get("calories") or 0 for e in meals), 1),
        "protein_g": round(sum(e.get("protein_g") or 0 for e in meals), 1),
        "spend": round(sum(float(e.get("amount") or 0) for e in meals), 2),
        "currency": currency,
        "targets": (store.profile(uid).get("nutrition_targets") or {})[0] if isinstance(
            store.profile(uid).get("nutrition_targets"), list) else (store.profile(uid).get("nutrition_targets") or {}),
    }


@router.get("/food/history")
def history(x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    events = store.events(uid)
    return {"events": events, "recent_dishes": FoodHistoryEngine.recent(events)}


@router.get("/pantry")
def get_pantry(x_user_id: int | None = Header(default=None)):
    return {"items": store.pantry(user_id(x_user_id))}


@router.post("/pantry")
def add_pantry(body: dict, x_user_id: int | None = Header(default=None)):
    try:
        return store.add_pantry({
            "user_id": user_id(x_user_id),
            "name": body["name"],
            "ingredient_id": body.get("ingredient_id"),
            "quantity": body.get("quantity") or 0,
            "unit": body.get("unit") or "g",
        })
    except KeyError as exc:
        raise HTTPException(422, f"missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/shopping/create")
def shopping_create(body: dict, x_user_id: int | None = Header(default=None)):
    items = body.get("items") or []
    shop = store.add_list({
        "user_id": user_id(x_user_id),
        "recipe_id": body.get("recipe_id"),
        "items": items,
        "status": "open",
        "offers": commerce.search_products(items),
    })
    return shop


@router.post("/shopping/bought")
def shopping_bought(body: dict):
    shop = store.update_list(body.get("id"), {"status": "bought", "actual_total": body.get("actual_total")})
    if not shop:
        raise HTTPException(404, "list not found")
    return shop


@router.get("/stores")
def stores():
    return {"stores": [{"name": "Local Grocery", "city": "Dhanbad", "type": "grocery"}]}


@router.get("/products")
def products(q: str = ""):
    return {"products": commerce.search_products([{"name": q or "ingredient", "quantity": 1, "unit": "unit"}])}


@router.get("/profile")
def get_profile(x_user_id: int | None = Header(default=None)):
    return store.profile(user_id(x_user_id))


@router.put("/profile")
def put_profile(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    if "language" in body:
        body["language"] = i18n.normalize_language(body["language"])
    return store.save_profile(uid, body)


def _session(session_id: int) -> dict:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return session
