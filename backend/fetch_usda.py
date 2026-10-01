"""Pull USDA FoodData Central into data/usda_ingredients.json.

Nutrition source of truth for raw and basic foods. Public domain (CC0).
Does not download recipes. Requires USDA_API_KEY (DEMO_KEY is rate-limited).

  python backend/fetch_usda.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
NUTRIENTS = {
    "208": "calories",
    "1008": "calories",
    "203": "protein_g",
    "1003": "protein_g",
    "205": "carbs_g",
    "1005": "carbs_g",
    "204": "fat_g",
    "1004": "fat_g",
}

QUERIES = [
    "chicken breast", "paneer", "chickpea", "rice", "tomato", "onion", "garlic",
    "ginger", "basil", "soy sauce", "mustard oil", "wheat flour", "lentil",
    "eggplant", "potato", "butter", "yogurt", "banana", "egg", "milk",
    "turmeric", "cumin", "coriander", "mustard seed", "green chili", "spinach",
    "cauliflower", "peas", "coconut", "peanut",
]


def main() -> None:
    key = os.getenv("USDA_API_KEY", "DEMO_KEY")
    page_size = int(os.getenv("USDA_PAGE_SIZE", "25"))
    out_dir = ROOT / os.getenv("DATA_DIR", "data")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with httpx.Client(timeout=40) as client:
        for query in QUERIES:
            response = client.get(SEARCH, params={
                "api_key": key,
                "query": query,
                "pageSize": page_size,
                "dataType": "Foundation,SR Legacy",
            })
            response.raise_for_status()
            for food in response.json().get("foods") or []:
                rows.append(normalize(food, query))
            time.sleep(0.4)
    path = out_dir / "usda_ingredients.json"
    path.write_text(json.dumps(rows, indent=2))
    print(f"wrote {len(rows)} rows to {path}")


def normalize(food: dict, query: str) -> dict:
    nutrition = {}
    for nutrient in food.get("foodNutrients") or []:
        number = str(nutrient.get("nutrientNumber") or nutrient.get("number") or "")
        key = NUTRIENTS.get(number)
        if key and nutrient.get("value") is not None:
            nutrition[key] = nutrient["value"]
    return {
        "canonical_name": food.get("description"),
        "category": food.get("foodCategory"),
        "aliases": [query],
        "nutrition_data": nutrition,
        "source": "usda_fdc",
        "source_id": str(food.get("fdcId")),
        "license": "CC0-1.0",
        "data_type": food.get("dataType"),
    }


if __name__ == "__main__":
    main()
