from __future__ import annotations

from copy import deepcopy

# Unit prices in INR per stated unit. Estimates, labelled as such.
UNIT_PRICE_INR = {
    "Chicken": 0.32,       # per g
    "Paneer": 0.40,
    "Chickpea": 0.12,
    "Rice": 0.06,
    "Tomato": 0.04,
    "Onion": 0.03,
    "Garlic": 0.20,
    "Ginger": 0.15,
    "Basil": 0.80,
    "Soy sauce": 0.25,     # per ml
    "Mustard oil": 0.18,
    "Wheat flour": 0.05,
    "Sattu": 0.10,
    "Eggplant": 0.04,
    "Potato": 0.03,
    "Lentil": 0.12,
    "Butter": 0.60,
    "Yogurt": 0.08,
    "Fish": 0.45,
    "Banana": 0.10,
}


def _norm(name: str) -> str:
    return (name or "").strip().lower()


class DietEngine:
    """Religious and cultural rules are configurable, not assumed universal."""

    @staticmethod
    def validate(recipe: dict, constraints: list[dict]) -> dict:
        failures = []
        ingredients = recipe.get("ingredients") or []
        for member in constraints:
            diet = (member.get("diet_profile") or "none").lower()
            allergies = {_norm(a) for a in (member.get("allergies") or [])}
            for ing in ingredients:
                name = ing.get("name") or ing.get("canonical_name")
                if ing.get("ingredient_verification") == "unverified" and (
                    diet in {"vegetarian", "vegan", "jain", "satvik", "gluten-free", "gluten_free"} or allergies
                ):
                    failures.append({"member": member.get("name"), "rule": "unverified_ingredient", "ingredient": name})
                if diet in {"vegetarian", "jain", "satvik"} and ing.get("animal_derived") and not ing.get("vegetarian"):
                    failures.append({"member": member.get("name"), "rule": diet, "ingredient": name})
                if diet == "vegan" and not ing.get("vegan", True):
                    failures.append({"member": member.get("name"), "rule": "vegan", "ingredient": name})
                if diet == "jain" and ing.get("jain_status") == "not_allowed":
                    failures.append({"member": member.get("name"), "rule": "jain", "ingredient": name})
                if diet in {"gluten-free", "gluten_free"} and ing.get("contains_gluten"):
                    failures.append({"member": member.get("name"), "rule": "gluten-free", "ingredient": name})
                allergen_hit = allergies.intersection({_norm(a) for a in (ing.get("allergens") or [])})
                if allergen_hit or _norm(name) in allergies:
                    failures.append({"member": member.get("name"), "rule": "allergen", "ingredient": name})
        return {"ok": not failures, "failures": failures}


# Weight conversions so non-metric units still get a partial estimate instead of null.
UNIT_GRAM_EQUIVALENT = {
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "l": 1000.0, "liter": 1000.0, "liters": 1000.0,
    "cup": 240.0, "cups": 240.0, "tbsp": 15.0, "tablespoon": 15.0, "tablespoons": 15.0,
    "tsp": 5.0, "teaspoon": 5.0, "teaspoons": 5.0,
    "oz": 28.35, "ounce": 28.35, "ounces": 28.35,
    "lb": 453.6, "pound": 453.6, "pounds": 453.6,
}
METRIC_UNITS = {"g", "gram", "grams", "ml", "milliliter", "milliliters"}


class NutritionEngine:
    @staticmethod
    def calculate(recipe: dict, servings: int | None = None) -> dict:
        """Partial estimates beat nulls: count what we can, flag what we cannot."""
        totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        missing = []
        estimated_units = []
        counted = 0
        total_items = len(recipe.get("ingredients") or [])
        for ing in recipe.get("ingredients") or []:
            n = ing.get("nutrition_data") or {}
            unit = _norm(ing.get("unit"))
            qty_raw = ing.get("quantity")
            if not n or qty_raw is None:
                missing.append(ing.get("name") or "unknown ingredient")
                continue
            qty = float(qty_raw)
            if unit in METRIC_UNITS:
                grams = qty
            elif unit in UNIT_GRAM_EQUIVALENT:
                grams = qty * UNIT_GRAM_EQUIVALENT[unit]
                estimated_units.append(ing.get("name") or unit)
            else:
                missing.append(ing.get("name") or "unknown ingredient")
                continue
            factor = grams / 100.0
            totals["calories"] += float(n.get("calories") or 0) * factor
            totals["protein_g"] += float(n.get("protein_g") or 0) * factor
            totals["carbs_g"] += float(n.get("carbs_g") or 0) * factor
            totals["fat_g"] += float(n.get("fat_g") or 0) * factor
            counted += 1
        servings = servings or int(recipe.get("servings") or 2)
        per_serving = {k: round(v / max(servings, 1), 1) for k, v in totals.items()}
        coverage = round(counted / total_items, 2) if total_items else 0.0
        return {
            "servings": servings,
            "total": {k: round(v, 1) for k, v in totals.items()},
            "per_serving": per_serving,
            "source": "ingredient_database" if not missing else "partial_ingredient_database",
            "complete": not missing,
            "coverage": coverage,
            "counted_ingredients": counted,
            "converted_units": estimated_units,
            "missing_ingredients": missing,
        }


class BudgetEngine:
    @staticmethod
    def validate(recipe: dict, budget: float | None, currency: str = "INR") -> dict:
        cost = 0.0
        lines = []
        unpriced = []
        for ing in recipe.get("ingredients") or []:
            name = ing.get("name")
            qty = float(ing.get("quantity") or 0)
            unit_price = UNIT_PRICE_INR.get(name)
            unit = _norm(ing.get("unit"))
            priced_unit = unit in {"g", "gram", "grams", "ml", "milliliter", "milliliters"}
            line = round(qty * unit_price, 2) if unit_price is not None and priced_unit and ing.get("quantity") is not None else None
            if line is None:
                unpriced.append(name)
            else:
                cost += line
            lines.append({"name": name, "quantity": qty, "unit": ing.get("unit"), "line_inr": line})
        cost = round(cost, 2)
        complete = not unpriced
        ok = True if budget is None else complete and cost <= budget
        return {
            "ok": ok,
            "estimated": complete,
            "complete": complete,
            "amount": cost if complete else None,
            "known_subtotal": cost,
            "unpriced_ingredients": unpriced,
            "currency": currency,
            "budget": budget,
            "lines": lines,
        }


class PantryEngine:
    @staticmethod
    def missing(recipe: dict, pantry: list[dict]) -> dict:
        have = {}
        for row in pantry:
            key = (_norm(row["name"]), _norm(row.get("unit")))
            have[key] = have.get(key, 0) + float(row.get("quantity") or 0)
        missing = []
        covered = []
        for ing in recipe.get("ingredients") or []:
            name = ing.get("name")
            if ing.get("quantity") is None:
                missing.append({"name": name, "quantity": None, "unit": ing.get("unit"), "quantity_unspecified": True})
                continue
            need = float(ing.get("quantity") or 0)
            got = have.get((_norm(name), _norm(ing.get("unit"))), 0)
            if got + 1e-6 >= need:
                covered.append({"name": name, "quantity": need, "unit": ing.get("unit")})
            else:
                missing.append({
                    "name": name,
                    "quantity": round(need - got, 1),
                    "unit": ing.get("unit"),
                    "ingredient_id": ing.get("ingredient_id"),
                })
        return {"missing": missing, "covered": covered}


class FoodHistoryEngine:
    @staticmethod
    def recent(events: list[dict], limit: int = 8) -> list[str]:
        names = []
        for ev in events:
            if ev.get("event_type") in {"MEAL", "COOKED"}:
                dish = (ev.get("data") or {}).get("dish")
                if dish:
                    names.append(dish)
        return names[:limit]


class RecommendationEngine:
    """Candidate generation, hard filters, deterministic score. AI only explains."""

    @staticmethod
    def score(recipe: dict, profile: dict, pantry_fit: float, budget_ok: bool, diet_ok: bool) -> dict:
        if not diet_ok:
            return {"score": -1, "rejected": "diet"}
        cuisines = {k.lower(): v for k, v in ((profile.get("recommendation_memory") or {}).get("cuisines") or {}).items()}
        recent = [x.lower() for x in (profile.get("recent_dishes") or [])]
        cuisine = (recipe.get("cuisine") or "").lower()
        title = (recipe.get("canonical_name") or recipe.get("title") or "").lower()
        preference = cuisines.get(cuisine, 0.35)
        novelty = 0.25 if title not in recent else -0.35
        diversity = 0.2 if cuisine not in {"indian"} or preference < 0.8 else 0.05
        pantry = 0.3 * pantry_fit
        budget = 0.15 if budget_ok else -0.2
        exploration = float(profile.get("exploration_level") or 0.4)
        score = round(preference * 0.35 + novelty * exploration + diversity + pantry + budget, 3)
        return {
            "score": score,
            "parts": {
                "preference_fit": round(preference, 3),
                "novelty": novelty,
                "cuisine_diversity": diversity,
                "pantry_fit": round(pantry_fit, 3),
                "budget_fit": budget,
            },
        }


class CookingEngine:
    """State machine. The model may label a frame; the engine decides the transition.

    Vision labels are advisory input only. Low-confidence labels never move the
    state. Timers and spoken cues are derived from step data, not hardcoded.
    """

    @staticmethod
    def _step_seconds(step: dict | None) -> int:
        try:
            return int((step or {}).get("duration_seconds") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def timer_for(session: dict) -> dict | None:
        steps = session.get("steps") or []
        idx = int(session.get("current_step") or 1)
        step = steps[idx - 1] if 0 < idx <= len(steps) else None
        seconds = CookingEngine._step_seconds(step)
        if seconds <= 0:
            return None
        return {"step": idx, "seconds": seconds, "label": (step or {}).get("instruction") or ""}

    @staticmethod
    def cue(text_key: str, params: dict | None = None, language: str | None = None) -> dict:
        """Voice/TTS cue payload. Text lives in i18n catalogs, resolved server-side."""
        from i18n import t

        return {"cue": text_key, "params": params or {}, "language": language or "en",
                "text": t(text_key, params, language)}

    @staticmethod
    def transition(session: dict, vision: dict | None, action: str, *,
                   advance_states: set[str] | None = None,
                   rescue_states: set[str] | None = None,
                   hold_states: set[str] | None = None,
                   min_confidence: float = 0.6) -> dict:
        from config import VISION_ADVANCE_STATES, VISION_HOLD_STATES, VISION_MIN_CONFIDENCE, VISION_RESCUE_STATES

        advance_states = advance_states or VISION_ADVANCE_STATES
        rescue_states = rescue_states or VISION_RESCUE_STATES
        hold_states = hold_states or VISION_HOLD_STATES
        min_confidence = max(min_confidence, VISION_MIN_CONFIDENCE)

        state = deepcopy(session.get("state") or {})
        step = int(session.get("current_step") or 1)
        steps = session.get("steps") or []
        total = len(steps) or 1
        was_completed = session.get("status") == "completed"
        visual = ((vision or {}).get("visual_state") or "").strip().lower() or None
        confidence = float((vision or {}).get("confidence") or 0)
        trusted = bool(visual) and confidence >= min_confidence
        decision = "hold"
        cues = []
        rescue = state.get("rescue")

        if action == "complete":
            step = total
            decision = "complete"
        elif action == "next":
            if step >= total:
                decision = "complete"
            else:
                step += 1
                decision = "next"
        elif action == "prev":
            step = max(1, step - 1)
            decision = "prev"
        elif trusted and visual in rescue_states:
            decision = "rescue"
            rescue = "Reduce heat and move the pan off the burner."
            cues.append(CookingEngine.cue("cue.rescue", language=session.get("language")))
        elif trusted and visual in advance_states:
            # Model suggests readiness; the human still confirms by tapping next.
            decision = "suggest_next"
            cues.append(CookingEngine.cue("cue.looks_ready", language=session.get("language")))
        elif trusted and visual in hold_states:
            decision = "guide"
            cues.append(CookingEngine.cue("cue.keep_going", {"state": visual}, session.get("language")))
        elif visual:
            decision = "low_confidence_hold"

        # Completion happens only after the last step is finished, never on arrival.
        status = "completed" if decision == "complete" else ("completed" if was_completed else "active")
        state["step"] = step
        state["visual_state"] = visual
        state["visual_confidence"] = confidence if visual else None
        state["decision"] = decision
        if rescue:
            state["rescue"] = rescue
        current = steps[step - 1] if 0 < step <= len(steps) else {}
        timer = None
        if decision in {"next", "prev"} or (action == "start"):
            timer = CookingEngine.timer_for({"steps": steps, "current_step": step})
            if timer:
                minutes = timer["seconds"] / 60
                if minutes >= 1:
                    cues.append(CookingEngine.cue("cue.timer_started",
                                                  {"minutes": round(minutes)}, session.get("language")))
        if status == "completed":
            cues.append(CookingEngine.cue("cue.done", language=session.get("language")))
        return {
            "current_step": step,
            "status": status,
            "decision": decision,
            "instruction": current.get("instruction", ""),
            "timer": timer,
            "cues": cues,
            "state": state,
        }


class RecipeEngine:
    @staticmethod
    def attach(recipe: dict, ingredients: list[dict]) -> dict:
        by_name = {_norm(i["canonical_name"]): i for i in ingredients}
        alias = {}
        for i in ingredients:
            alias[_norm(i["canonical_name"])] = i
            for a in i.get("aliases") or []:
                alias[_norm(a)] = i
        out = deepcopy(recipe)
        resolved = []
        for ing in out.get("ingredients") or []:
            hit = next((alias[variant] for variant in _name_variants(ing.get("name")) if variant in alias), None)
            row = dict(ing)
            if hit:
                row.update({
                    "name": hit["canonical_name"],
                    "ingredient_id": hit["id"],
                    "nutrition_data": hit.get("nutrition_data") or {},
                    "vegetarian": bool(hit.get("vegetarian")),
                    "vegan": bool(hit.get("vegan")),
                    "animal_derived": bool(hit.get("animal_derived")),
                    "contains_gluten": bool(hit.get("contains_gluten")),
                    "contains_dairy": bool(hit.get("contains_dairy")),
                    "jain_status": hit.get("jain_status"),
                    "allergens": hit.get("allergens") or [],
                    "ingredient_verification": "verified",
                })
            else:
                row["ingredient_verification"] = "unverified"
            resolved.append(row)
        out["ingredients"] = resolved
        out["title"] = out.get("canonical_name") or out.get("title")
        return out


def _name_variants(name: str) -> list[str]:
    normalized = _norm(name)
    variants = [normalized]
    if normalized.endswith("ies") and len(normalized) > 3:
        variants.append(normalized[:-3] + "y")
    if normalized.endswith("oes") and len(normalized) > 3:
        variants.append(normalized[:-2])
    if normalized.endswith("s") and len(normalized) > 2:
        variants.append(normalized[:-1])
    return variants
