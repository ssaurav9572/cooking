"""Task prompts. Models return JSON only. Engines own arithmetic and dietary rules."""

SYSTEM = (
    "You are CookAI's structured generator. Return only JSON matching the requested schema. "
    "Do not invent nutrition totals, prices, or dietary legality. Those are computed by the backend. "
    "If an ingredient is uncertain, lower confidence instead of pretending."
)

RECIPE_GENERATION = """
Generate a recipe JSON for this request.
Request: {data}
Use only these canonical ingredient names when possible: {ingredients}
Return:
{{
  "title": str,
  "servings": int,
  "difficulty": "easy"|"medium"|"hard",
  "time_minutes": int,
  "cuisine": str,
  "ingredients": [{{"name": str, "quantity": number, "unit": "g"|"ml"|"pcs"}}],
  "steps": [{{"step": int, "instruction": str, "duration_seconds": int}}],
  "confidence": number
}}
Do not include nutrition or cost.
"""

EXPLAIN = """
Explain in 2 sentences why this dish fits the user. Do not change the recipe.
Profile: {profile}
Dish: {dish}
Return {{"explanation": str}}
"""

INTENT = """
Extract cooking intent. Return JSON:
{{"people": int, "budget": number|null, "ingredients": [str], "novelty": "low"|"medium"|"high", "meal": str}}
User: {text}
"""

TRANSLATE = """
Translate the source text to {target}. Keep meaning, tone, and any numbers exact.
Return {{"translated": str, "target_language": "{target}"}}
Source: {source_text}
"""

COOKING_VISION = """
You are looking at one frame from a live cooking session.
Current step instruction: {instruction}
Classify what you see. Allowed visual_state values: {states} (use "other" if none fit).
Return {{{{"visual_state": str, "confidence": number, "observation": str}}}}
If you cannot tell, return visual_state "other" with confidence below 0.5. Never guess upward.
"""

FOOD_DETECTION = """
Look at this photo of food items or a fridge interior.
List every distinct edible item you can identify with a confidence value.
Return {{"items": [{{"name": str, "confidence": number, "approx_quantity": number|null, "unit": str|null}}]}}
Only include items actually visible; do not assume staples.
"""
