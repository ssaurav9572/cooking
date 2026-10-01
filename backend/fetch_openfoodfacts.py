"""Pull packaged products from Open Food Facts into data/off_products.json.

Use for barcode, brand, label nutrients and allergens. Not a recipe source.
Keep source and license metadata. Send a real User-Agent.

  python backend/fetch_openfoodfacts.py
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

SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
QUERIES = ["atta", "basmati rice", "toor dal", "mustard oil", "paneer", "soy sauce"]


def main() -> None:
    agent = os.getenv("OFF_USER_AGENT", "CookAI/0.1 (local)")
    page_size = int(os.getenv("OFF_PAGE_SIZE", "20"))
    out_dir = ROOT / os.getenv("DATA_DIR", "data")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    headers = {"User-Agent": agent}
    with httpx.Client(timeout=40, headers=headers) as client:
        for query in QUERIES:
            response = client.get(SEARCH, params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": page_size,
                "fields": "code,product_name,brands,categories,ingredients_text,nutriments,allergens_tags,countries_tags",
            })
            response.raise_for_status()
            for product in response.json().get("products") or []:
                rows.append(normalize(product, query))
            time.sleep(1)
    path = out_dir / "off_products.json"
    path.write_text(json.dumps(rows, indent=2))
    print(f"wrote {len(rows)} products to {path}")


def normalize(product: dict, query: str) -> dict:
    nutriments = product.get("nutriments") or {}
    return {
        "barcode": product.get("code"),
        "product_name": product.get("product_name"),
        "brand": product.get("brands"),
        "category": product.get("categories"),
        "ingredients_text": product.get("ingredients_text"),
        "allergens": product.get("allergens_tags") or [],
        "nutrition_data": {
            "calories": nutriments.get("energy-kcal_100g"),
            "protein_g": nutriments.get("proteins_100g"),
            "carbs_g": nutriments.get("carbohydrates_100g"),
            "fat_g": nutriments.get("fat_100g"),
            "per": "100g",
        },
        "query": query,
        "source": "open_food_facts",
        "source_id": product.get("code"),
        "license": "ODbL/DbCL — keep attribution before commercial use",
    }


if __name__ == "__main__":
    main()
