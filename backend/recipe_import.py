"""User-supplied recipe parsing. No network fetches or recipe-site scraping."""

from __future__ import annotations

import json
import re

MAX_IMPORT_CHARS = 20000
MAX_INGREDIENTS = 80
MAX_STEPS = 80

_SECTION_INGREDIENTS = re.compile(r"^(ingredients?|what you(?:'|’)ll need)\s*:?$", re.I)
_SECTION_STEPS = re.compile(r"^(instructions?|directions?|method|steps?)\s*:?$", re.I)
_SERVINGS = re.compile(r"(?:serves?|servings?|yield)\s*[:=]?\s*(\d{1,3})", re.I)
_TIME = re.compile(r"(prep|preparation|cook|cooking)\s*(?:time)?\s*[:=]?\s*(\d{1,4})\s*(?:minutes?|mins?)?", re.I)
_UNITS = {
    "g": "g", "gram": "g", "grams": "g", "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "l": "l", "liter": "l", "liters": "l",
    "cup": "cup", "cups": "cup", "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "piece": "pcs", "pieces": "pcs",
    "pcs": "pcs", "pc": "pcs", "clove": "cloves", "cloves": "cloves", "can": "can", "cans": "can",
    "slice": "slices", "slices": "slices", "pinch": "pinch", "pinches": "pinch",
    "bunch": "bunch", "bunches": "bunch", "handful": "handful", "handfuls": "handful",
    "stalk": "stalks", "stalks": "stalks", "package": "package", "packages": "package",
    "packet": "packet", "packets": "packet", "bottle": "bottle", "bottles": "bottle",
    "tin": "tin", "tins": "tin", "ounce": "oz", "ounces": "oz", "oz": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb",
}
_SIZE_WORDS = {"small", "medium", "large", "ripe", "heaped", "level", "big"}
_QUANTITY_LINE = re.compile(
    r"^\s*(?P<quantity>(?:\d+\s+)?\d+\s*/\s*\d+|\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?\s+(?P<name>.+?)\s*$"
)


def parse_recipe_text(text: str) -> tuple[dict, list[str], str]:
    """Parse a JSON/JSON-LD recipe or a plain-text recipe into the app's recipe shape."""
    if not isinstance(text, str) or not text.strip():
        return _empty_recipe(), ["Paste a recipe as text or JSON to start."], "plain_text"
    if len(text) > MAX_IMPORT_CHARS:
        raise ValueError(f"Recipe input is limited to {MAX_IMPORT_CHARS} characters.")

    stripped = text.strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = None
    candidate = _find_recipe(data) if data is not None else None
    if candidate is not None:
        recipe = _from_structured(candidate)
        source_type = "user_json_import"
    else:
        recipe = _from_plain_text(text)
        source_type = "user_text_import"
    warnings = _quality_warnings(recipe)
    return recipe, warnings, source_type


def recipe_from_review(title: str, cuisine: str, ingredients_text: str, steps_text: str, servings: int, prep_minutes: int, cook_minutes: int) -> dict:
    """Rebuild the user-edited fields and apply bounded server-side validation."""
    if not all(isinstance(value, str) for value in (title, cuisine, ingredients_text, steps_text)):
        raise ValueError("Title, cuisine, ingredients, and steps must be text.")
    if len(ingredients_text) > MAX_IMPORT_CHARS or len(steps_text) > MAX_IMPORT_CHARS:
        raise ValueError(f"Ingredients and steps are limited to {MAX_IMPORT_CHARS} characters each.")
    if len(ingredients_text.splitlines()) > MAX_INGREDIENTS or len(steps_text.splitlines()) > MAX_STEPS:
        raise ValueError(f"A recipe can have at most {MAX_INGREDIENTS} ingredients and {MAX_STEPS} steps.")
    if len(title.strip()) > 200 or len(cuisine.strip()) > 80:
        raise ValueError("Recipe title is limited to 200 characters and cuisine to 80.")
    ingredients = [parse_ingredient_line(line) for line in (ingredients_text or "").splitlines() if line.strip()]
    steps = []
    for line in (steps_text or "").splitlines():
        instruction = _clean_step(line)
        if instruction:
            steps.append({"step": len(steps) + 1, "instruction": instruction, "duration_seconds": 0})
    recipe = {
        "canonical_name": _clean(title, 200),
        "cuisine": _clean(cuisine, 80),
        "servings": _bounded_int(servings, 1, 50, 2),
        "prep_minutes": _bounded_int(prep_minutes, 0, 1440, 0),
        "cook_minutes": _bounded_int(cook_minutes, 0, 1440, 0),
        "difficulty": "easy",
        "ingredients": ingredients,
        "steps": steps,
    }
    if not recipe["canonical_name"]:
        raise ValueError("A recipe title is required.")
    if not ingredients:
        raise ValueError("Add at least one ingredient.")
    if not steps:
        raise ValueError("Add at least one cooking step.")
    if len(ingredients) > MAX_INGREDIENTS:
        raise ValueError(f"A recipe can have at most {MAX_INGREDIENTS} ingredients.")
    if len(steps) > MAX_STEPS:
        raise ValueError(f"A recipe can have at most {MAX_STEPS} steps.")
    return recipe


def format_ingredient(item: dict) -> str:
    quantity = item.get("quantity")
    unit = item.get("unit") or ""
    name = item.get("name") or ""
    prefix = f"{quantity:g} {unit} ".strip() if isinstance(quantity, (int, float)) and quantity > 0 else ""
    notes = item.get("notes")
    suffix = f", {notes}" if notes else ""
    return f"{prefix}{name}{suffix}".strip()


def _find_recipe(data):
    if isinstance(data, list):
        for item in data:
            hit = _find_recipe(item)
            if hit is not None:
                return hit
        return None
    if not isinstance(data, dict):
        return None
    graph = data.get("@graph")
    if isinstance(graph, list):
        hit = _find_recipe(graph)
        if hit is not None:
            return hit
    schema_type = data.get("@type") or data.get("type")
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    if any(str(kind).lower().endswith("recipe") for kind in types if kind):
        return data
    recipe_keys = {"recipeIngredient", "recipeInstructions", "ingredients", "instructions", "steps"}
    if recipe_keys.intersection(data) and (data.get("name") or data.get("title")):
        return data
    return None


def _from_structured(data: dict) -> dict:
    ingredient_rows = data.get("recipeIngredient") or data.get("ingredients") or []
    ingredients = []
    for item in ingredient_rows:
        if isinstance(item, str):
            ingredients.append(parse_ingredient_line(item))
        elif isinstance(item, dict):
            ingredients.append({
                "name": _clean(item.get("name") or item.get("ingredient") or "ingredient", 120),
                "quantity": _number_or_none(item.get("quantity")),
                "unit": _clean(item.get("unit") or "", 20),
                "notes": _clean(item.get("notes") or "", 120),
            })
    raw_steps = data.get("recipeInstructions") or data.get("instructions") or data.get("steps") or []
    step_lines = _flatten_steps(raw_steps)
    prep_minutes = _duration_minutes(data.get("prepTime"))
    cook_minutes = _duration_minutes(data.get("cookTime"))
    servings = data.get("recipeYield") or data.get("servings") or 2
    if isinstance(servings, list):
        servings = servings[0] if servings else 2
    serving_match = re.search(r"\d{1,3}", str(servings))
    return {
        "canonical_name": _clean(data.get("name") or data.get("title") or "", 200),
        "cuisine": _clean(data.get("recipeCuisine") or data.get("cuisine") or "", 80),
        "servings": _bounded_int(int(serving_match.group()) if serving_match else 2, 1, 50, 2),
        "prep_minutes": _bounded_int(prep_minutes, 0, 1440, 0),
        "cook_minutes": _bounded_int(cook_minutes, 0, 1440, 0),
        "difficulty": "easy",
        "ingredients": ingredients[:MAX_INGREDIENTS],
        "steps": [{"step": i, "instruction": line, "duration_seconds": 0} for i, line in enumerate(step_lines[:MAX_STEPS], 1)],
    }


def _flatten_steps(raw) -> list[str]:
    if isinstance(raw, str):
        return [_clean_step(line) for line in raw.splitlines() if _clean_step(line)]
    if not isinstance(raw, list):
        raw = [raw]
    out = []
    for item in raw:
        if isinstance(item, str):
            out.extend(_flatten_steps(item))
        elif isinstance(item, dict):
            nested = item.get("itemListElement")
            if nested:
                out.extend(_flatten_steps(nested))
            else:
                instruction = item.get("text") or item.get("name") or item.get("instruction")
                if instruction:
                    out.append(_clean_step(str(instruction)))
    return [line for line in out if line]


def _from_plain_text(text: str) -> dict:
    lines = [_clean_step(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    title = ""
    ingredient_lines = []
    step_lines = []
    current_section = None
    for index, line in enumerate(lines):
        clean = line.lstrip("# ").strip()
        if _SECTION_INGREDIENTS.match(clean):
            current_section = "ingredients"
            continue
        if _SECTION_STEPS.match(clean):
            current_section = "steps"
            continue
        if current_section is None:
            if not title and not re.match(r"^(serves?|servings?|yield|prep|cook)\b", clean, re.I):
                title = clean
            continue
        if current_section == "ingredients":
            ingredient_lines.append(line)
        else:
            step_lines.append(line)

    ingredients = [parse_ingredient_line(line) for line in ingredient_lines if line]
    steps = [{"step": i, "instruction": _clean_step(line), "duration_seconds": 0} for i, line in enumerate(step_lines, 1)]
    servings_match = _SERVINGS.search(text)
    times = {
        "prep" if kind.lower().startswith("prep") else "cook": int(value)
        for kind, value in _TIME.findall(text)
    }
    return {
        "canonical_name": _clean(title, 200),
        "cuisine": "",
        "servings": _bounded_int(int(servings_match.group(1)) if servings_match else 2, 1, 50, 2),
        "prep_minutes": _bounded_int(times.get("prep", 0), 0, 1440, 0),
        "cook_minutes": _bounded_int(times.get("cook", 0), 0, 1440, 0),
        "difficulty": "easy",
        "ingredients": ingredients[:MAX_INGREDIENTS],
        "steps": steps[:MAX_STEPS],
    }


def parse_ingredient_line(line: str) -> dict:
    line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(line)).strip()
    line = re.sub(r"\s+", " ", line)
    match = _QUANTITY_LINE.match(line)
    quantity = None
    unit = ""
    name = line
    descriptor_note = ""
    if match:
        quantity = _parse_quantity(match.group("quantity"))
        raw_unit = (match.group("unit") or "").lower()
        name = match.group("name").strip()
        unit = _UNITS.get(raw_unit, "")
        if not unit and raw_unit:
            if raw_unit in _SIZE_WORDS:
                descriptor_note = raw_unit
            else:
                name = f"{raw_unit} {name}"
    if not unit and quantity is not None:
        unit = "pcs"
    parts = [part.strip() for part in name.split(",", 1)]
    name = re.sub(r"\s+", " ", parts[0]).strip(" .;:")
    notes = ", ".join(part for part in [descriptor_note, _clean(parts[1], 120) if len(parts) > 1 else ""] if part)
    return {"name": _clean(name or line, 120), "quantity": quantity, "unit": unit, "notes": notes}


def _parse_quantity(raw: str) -> float | None:
    try:
        raw = raw.strip()
        if " " in raw:
            whole, fraction = raw.split(None, 1)
            return float(whole) + _parse_quantity(fraction)
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            return float(numerator) / float(denominator)
        return float(raw)
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _duration_minutes(value) -> int:
    """Accept ISO 8601 durations (Schema.org) and simple numeric minute values."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", text, re.I)
    if match:
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    time_match = re.search(r"(\d+)\s*(?:minutes?|mins?)", text, re.I)
    return int(time_match.group(1)) if time_match else 0


def _quality_warnings(recipe: dict) -> list[str]:
    warnings = []
    if not recipe.get("canonical_name"):
        warnings.append("Recipe title was not found; add one before saving.")
    if not recipe.get("ingredients"):
        warnings.append("Ingredient section was not found; add ingredients before saving.")
    elif any(item.get("quantity") is None for item in recipe["ingredients"]):
        warnings.append("Some ingredient amounts are missing or written as 'to taste'. Review them.")
    if not recipe.get("steps"):
        warnings.append("Cooking steps were not found; add steps before saving.")
    return warnings


def _empty_recipe() -> dict:
    return {"canonical_name": "", "servings": 2, "prep_minutes": 0, "cook_minutes": 0, "difficulty": "easy", "ingredients": [], "steps": []}


def _number_or_none(value):
    try:
        number = _parse_quantity(str(value)) if isinstance(value, str) else float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _bounded_int(value, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return fallback


def _clean(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _clean_step(value: str) -> str:
    value = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(value)).strip()
    return _clean(value, 1000)
