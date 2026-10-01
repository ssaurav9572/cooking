"""Bounded recipe-import judgments. Application policy remains deterministic."""

from __future__ import annotations

import httpx

from config import JEV_API_KEY, JEV_MODEL

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MIN_DECISION_CONFIDENCE = 0.75


def judge_recipe_import(text: str, recipe: dict) -> dict:
    """Classify and score an import in one optional Jev request, with a local fallback."""
    facts = _facts(recipe)
    if not JEV_API_KEY:
        return _local_judgment(facts)

    # Send a short excerpt and parser facts, not a photo, account data, or full history.
    state = {
        "recipe_excerpt": text[:4500],
        "parsed_fields": facts,
    }
    request = {
        "model": JEV_MODEL,
        "state": state,
        "questions": {
            "content_kind": {
                "type": "choice",
                "instructions": "What best describes the submitted content?",
                "criteria": {
                    "recipe": "A recipe with ingredients and cooking instructions.",
                    "not_a_recipe": "Not a recipe, such as a shopping list or unrelated text.",
                    "unclear": "The content is too ambiguous to classify confidently.",
                },
            },
            "completeness": {
                "type": "score",
                "instructions": "How complete and actionable is the parsed recipe?",
                "criteria": [
                    "Essential recipe fields are mostly absent.",
                    "Either ingredients or cooking steps are missing.",
                    "Ingredients and steps exist but important details are sparse.",
                    "A title, ingredients, and usable cooking steps are present.",
                ],
            },
            "needs_review": {
                "type": "noul",
                "instructions": "Should a person inspect this recipe before saving it, due to ambiguous amounts, ingredients, or instructions?",
            },
        },
    }
    try:
        response = httpx.post(
            JEV_ENDPOINT,
            headers={"Authorization": f"Bearer {JEV_API_KEY}"},
            json=request,
            timeout=8,
        )
        response.raise_for_status()
        answers = response.json().get("answers") or {}
        normalized = _normalize_jev(answers)
        if normalized:
            return {"provider": "jev", "model": JEV_MODEL, **normalized}
    except Exception:
        # Import remains available if Jev is not configured or temporarily unavailable.
        pass
    return _local_judgment(facts)


def import_policy(recipe: dict, judgment: dict) -> dict:
    """Make the action explicit; Jev can advise, but never saves a recipe."""
    has_title = bool((recipe.get("canonical_name") or "").strip())
    has_ingredients = bool(recipe.get("ingredients"))
    has_steps = bool(recipe.get("steps"))
    can_save = has_title and has_ingredients and has_steps
    content_kind = judgment.get("content_kind") or {}
    quality = judgment.get("completeness") or {}
    review = judgment.get("needs_review") or {}
    confidence = float(content_kind.get("confidence") or 0)
    likely_not_recipe = content_kind.get("choice") == "not_a_recipe" and confidence >= MIN_DECISION_CONFIDENCE
    warning = None
    if not can_save:
        warning = "Add a title, at least one ingredient, and at least one cooking step before saving."
    elif likely_not_recipe:
        warning = "The decision check is unsure this is a recipe. Review every field before saving."
    elif float(review.get("noul") or 0) >= 0.5:
        warning = "Some amounts or instructions may need correction. Review the parsed recipe before saving."
    return {
        "status": "ready_for_review" if can_save else "needs_more_information",
        "can_save": can_save,
        "review_required": True,
        "warning": warning,
        "signals": {
            "content_kind": content_kind,
            "completeness": quality,
            "needs_review": review,
            "minimum_confidence_for_not_recipe": MIN_DECISION_CONFIDENCE,
        },
    }


def _facts(recipe: dict) -> dict:
    ingredients = recipe.get("ingredients") or []
    steps = recipe.get("steps") or []
    return {
        "has_title": bool(recipe.get("canonical_name")),
        "ingredient_count": len(ingredients),
        "step_count": len(steps),
        "missing_quantity_count": sum(1 for item in ingredients if item.get("quantity") is None),
    }


def _normalize_jev(answers: dict) -> dict | None:
    kind = answers.get("content_kind") or {}
    score = answers.get("completeness") or {}
    review = answers.get("needs_review") or {}
    choice = kind.get("choice")
    if choice not in {"recipe", "not_a_recipe", "unclear"}:
        return None
    try:
        confidence = max(0.0, min(1.0, float(kind.get("confidence", 0))))
        score_value = max(0.0, min(3.0, float(score.get("score", 0))))
        review_probability = max(0.0, min(1.0, float(review.get("noul", 0))))
    except (TypeError, ValueError):
        return None
    return {
        "content_kind": {
            "type": "choice",
            "choice": choice,
            "confidence": confidence,
            "probabilities": kind.get("probabilities") or {},
        },
        "completeness": {
            "type": "score",
            "score": score_value,
            "confidence": max(0.0, min(1.0, float(score.get("confidence", 0)))),
            "probabilities": score.get("probabilities") or {},
        },
        "needs_review": {"type": "noul", "noul": review_probability},
    }


def _local_judgment(facts: dict) -> dict:
    ingredients = facts["ingredient_count"]
    steps = facts["step_count"]
    has_title = facts["has_title"]
    complete_sections = int(ingredients > 0) + int(steps > 0)
    score = min(3, complete_sections + int(has_title and complete_sections == 2))
    if ingredients and steps and has_title:
        choice = "recipe"
    elif ingredients or steps:
        choice = "unclear"
    else:
        choice = "not_a_recipe"
    choices = ["recipe", "not_a_recipe", "unclear"]
    probabilities = {option: (0.5 if option == choice else 0.25) for option in choices}
    needs_review = bool(facts["missing_quantity_count"] or score < 3)
    return {
        "provider": "local",
        "model": "deterministic-import-check",
        "content_kind": {
            "type": "choice",
            "choice": choice,
            "confidence": 0.5,
            "probabilities": probabilities,
        },
        "completeness": {
            "type": "score",
            "score": float(score),
            "confidence": 1.0,
            "probabilities": {str(score): 1.0},
        },
        "needs_review": {"type": "noul", "noul": 0.85 if needs_review else 0.15},
    }
