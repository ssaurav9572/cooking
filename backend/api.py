"""HTTP surface for the vertical slice. Auth is X-User-Id until JWT is wired."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

import ai
from commerce import commerce
from decision import import_policy, judge_recipe_import
from database import mem
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

router = APIRouter(prefix="/api")


def user_id(x_user_id: int | None) -> int:
    return x_user_id or 1


def household_constraints(uid: int) -> list[dict]:
    # Slice uses household 1. A vegetarian member hard-filters meat.
    return [m for m in mem.members if m["household_id"] == 1]


def _recipe_payload(recipe: dict, budget: float | None, people: int, uid: int) -> dict:
    attached = RecipeEngine.attach(recipe, mem.ingredients)
    attached["servings"] = people
    diet = DietEngine.validate(attached, household_constraints(1))
    nutrition = NutritionEngine.calculate(attached, people)
    cost = BudgetEngine.validate(attached, budget)
    pantry = PantryEngine.missing(attached, [p for p in mem.pantry if p["user_id"] == uid])
    fit = 1 - (len(pantry["missing"]) / max(len(attached["ingredients"]), 1))
    scored = RecommendationEngine.score(attached, mem.profiles.get(uid, {}), fit, cost["ok"], diet["ok"])
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


@router.post("/chat")
def chat(body: dict, x_user_id: int | None = Header(default=None)):
    intent = ai.generate("intent", {"text": body.get("message", "")}, user_id(x_user_id))
    return {"intent": intent, "next": "POST /api/recipe/generate"}


@router.post("/recipe/generate")
def generate(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    text = body.get("message") or ""
    intent = body.get("intent") or ai.generate("intent", {"text": text}, uid)
    people = int(body.get("people") or intent.get("people") or 2)
    budget = body.get("budget", intent.get("budget"))
    if budget is not None:
        budget = float(budget)
    have = {p["name"].lower() for p in mem.pantry if p["user_id"] == uid}
    for name in intent.get("ingredients") or []:
        have.add(name.lower())
    cards = []
    for recipe in _available_recipes(uid):
        card = _recipe_payload(recipe, budget, people, uid)
        names = {i["name"].lower() for i in card["ingredients"]}
        if have and not (names & have) and body.get("require_pantry"):
            continue
        if not card["diet"]["ok"]:
            continue
        cards.append(card)
    cards.sort(key=lambda c: c["score"]["score"], reverse=True)
    top = cards[:3]
    profile = mem.profiles.get(uid, {})
    for card in top:
        card["explanation"] = ai.generate(
            "explanation",
            {"profile": profile, "dish": {"title": card["title"], "cuisine": card["cuisine"]}},
            uid,
        ).get("explanation")
    return {
        "intent": intent,
        "candidates": top,
        "note": "Scores and nutrition are deterministic. Explanations may come from the AI router.",
    }


def _available_recipes(uid: int) -> list[dict]:
    return [r for r in mem.recipes if r.get("owner_user_id") in (None, uid)]


@router.post("/recipes/import/preview")
def recipe_import_preview(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    source = body.get("text")
    if not isinstance(source, str):
        raise HTTPException(422, "recipe text must be a string")
    try:
        recipe, warnings, source_type = parse_recipe_text(source)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from exc
    judgment = judge_recipe_import(source, recipe)
    policy = import_policy(recipe, judgment)
    attached_preview = RecipeEngine.attach(recipe, mem.ingredients)
    unresolved = sorted({item.get("name", "").strip() for item in attached_preview.get("ingredients", []) if item.get("ingredient_verification") == "unverified"})
    if unresolved:
        warnings.append("CookAI could not match these ingredients to its catalog: " + ", ".join(unresolved[:8]) + ". Unverified ingredients may keep this recipe out of household recommendations with diet or allergy rules until you correct them.")
    if any((item.get("unit") or "").strip().lower() not in {"g", "gram", "grams", "ml", "milliliter", "milliliters"} for item in recipe.get("ingredients", [])):
        warnings.append("CookAI only estimates nutrition and ingredient cost for catalog items measured in g or ml. Other units remain unestimated.")
    preview_id = mem.next_id("recipe_import")
    mem.pending_recipe_imports[preview_id] = {
        "user_id": uid,
        "source_type": source_type,
        "recipe": recipe,
    }
    while len(mem.pending_recipe_imports) > 32:
        mem.pending_recipe_imports.pop(next(iter(mem.pending_recipe_imports)))
    return {
        "preview_id": preview_id,
        "recipe": recipe,
        "warnings": warnings,
        "decision": policy,
        "decision_provider": judgment.get("provider"),
        "decision_model": judgment.get("model"),
    }


@router.post("/recipes/import/commit")
def recipe_import_commit(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    preview_id = body.get("preview_id")
    if not isinstance(preview_id, int):
        raise HTTPException(404, "recipe import preview not found")
    pending = mem.pending_recipe_imports.get(preview_id)
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

    recipe.update({
        "id": mem.next_id("recipe"),
        "owner_user_id": uid,
        "source_type": pending["source_type"],
        "confidence": 0.8,
    })
    mem.recipes.append(recipe)
    del mem.pending_recipe_imports[preview_id]
    return {"recipe": recipe, "saved": True, "note": "Saved to your private recipe collection in this running app."}


@router.post("/recipe/{recipe_id}/start")
def start(recipe_id: int, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    recipe = next((r for r in _available_recipes(uid) if r["id"] == recipe_id), None)
    if not recipe:
        raise HTTPException(404, "recipe not found")
    session = {
        "id": mem.next_id("session"),
        "user_id": uid,
        "recipe_id": recipe_id,
        "title": recipe["canonical_name"],
        "current_step": 1,
        "status": "active",
        "steps": recipe["steps"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "state": {"step": 1},
    }
    mem.sessions.append(session)
    return session


@router.post("/cooking/{session_id}/message")
def cooking_message(session_id: int, body: dict):
    session = _session(session_id)
    action = body.get("action") or "next"
    result = CookingEngine.transition(session, None, action)
    session.update(result)
    return session


@router.post("/cooking/{session_id}/vision")
def cooking_vision(session_id: int, body: dict):
    session = _session(session_id)
    # Frame bytes are not stored. Caller sends a label or the router classifies.
    vision = body.get("vision") or {"visual_state": body.get("visual_state") or "incomplete", "confidence": 0.5}
    result = CookingEngine.transition(session, vision, body.get("action") or "vision")
    session.update(result)
    return session


@router.post("/meal/log")
def log_meal(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    nutrition = body.get("nutrition") or {}
    per = nutrition.get("per_serving") or nutrition
    event = {
        "id": mem.next_id("event"),
        "user_id": uid,
        "event_type": body.get("event_type") or "COOKED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "reference_id": body.get("recipe_id"),
        "calories": per.get("calories"),
        "protein_g": per.get("protein_g"),
        "carbs_g": per.get("carbs_g"),
        "fat_g": per.get("fat_g"),
        "amount": (body.get("estimated_cost") or {}).get("amount"),
        "currency": "INR",
        "data": {
            "dish": body.get("title"),
            "servings": body.get("servings_eaten") or 1,
            "source": "cooked_in_app",
            "recipe_id": body.get("recipe_id"),
            "cuisine": body.get("cuisine"),
        },
    }
    mem.events.insert(0, event)
    profile = mem.profiles.setdefault(uid, {})
    recent = profile.setdefault("recent_dishes", [])
    if body.get("title"):
        recent.insert(0, body["title"])
        profile["recent_dishes"] = recent[:8]
    return event


@router.get("/food/today")
def today(x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    meals = [e for e in mem.events if e["user_id"] == uid and e["event_type"] in {"MEAL", "COOKED", "SNACK"}]
    return {
        "meals": meals,
        "calories": round(sum(e.get("calories") or 0 for e in meals), 1),
        "protein_g": round(sum(e.get("protein_g") or 0 for e in meals), 1),
        "spend": round(sum(e.get("amount") or 0 for e in meals), 2),
        "currency": "INR",
    }


@router.get("/food/history")
def history(x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    events = [e for e in mem.events if e["user_id"] == uid]
    return {"events": events, "recent_dishes": FoodHistoryEngine.recent(events)}


@router.get("/pantry")
def get_pantry(x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    return {"items": [p for p in mem.pantry if p["user_id"] == uid]}


@router.post("/pantry")
def add_pantry(body: dict, x_user_id: int | None = Header(default=None)):
    row = {
        "id": mem.next_id("pantry"),
        "user_id": user_id(x_user_id),
        "name": body["name"],
        "ingredient_id": body.get("ingredient_id"),
        "quantity": body.get("quantity") or 0,
        "unit": body.get("unit") or "g",
    }
    mem.pantry.append(row)
    return row


@router.post("/shopping/create")
def shopping_create(body: dict, x_user_id: int | None = Header(default=None)):
    items = body.get("items") or []
    shop = {
        "id": mem.next_id("list"),
        "user_id": user_id(x_user_id),
        "recipe_id": body.get("recipe_id"),
        "items": items,
        "status": "open",
        "offers": commerce.search_products(items),
    }
    mem.lists.append(shop)
    return shop


@router.post("/shopping/bought")
def shopping_bought(body: dict):
    shop = next((s for s in mem.lists if s["id"] == body.get("id")), None)
    if not shop:
        raise HTTPException(404, "list not found")
    shop["status"] = "bought"
    shop["actual_total"] = body.get("actual_total")
    return shop


@router.get("/stores")
def stores():
    return {"stores": [{"name": "Local Grocery", "city": "Dhanbad", "type": "grocery"}]}


@router.get("/products")
def products(q: str = ""):
    return {"products": commerce.search_products([{"name": q or "ingredient", "quantity": 1, "unit": "unit"}])}


@router.get("/profile")
def get_profile(x_user_id: int | None = Header(default=None)):
    return mem.profiles.get(user_id(x_user_id), {})


@router.put("/profile")
def put_profile(body: dict, x_user_id: int | None = Header(default=None)):
    uid = user_id(x_user_id)
    mem.profiles.setdefault(uid, {}).update(body)
    return mem.profiles[uid]


def _session(session_id: int) -> dict:
    session = next((s for s in mem.sessions if s["id"] == session_id), None)
    if not session:
        raise HTTPException(404, "session not found")
    return session
