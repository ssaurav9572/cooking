# CookAI

Small monolith. MySQL is the food memory. External APIs are inputs. AI returns JSON. `engine.py` validates diet, nutrition, budget, pantry and cooking state.

## Run the vertical slice

```bash
cd cookai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --app-dir backend --reload --port 8000
```

Open http://127.0.0.1:8000

Without MySQL the API uses the in-process seed (Dal Tadka, Litti Chokha, Thai Basil Chicken, Paneer Butter Masala). A vegetarian household member rejects chicken dishes. Nutrition and rupee estimates are computed in code, not by the model.

Optional keys in `.env`: `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`. If both are empty, explanations use the deterministic fallback.
Optional `JEV_API_KEY` enables one Jev typed-decision request during recipe import. The app sends only a short text excerpt and parsed field counts. Without the key, deterministic local checks produce the same decision shape.

## MySQL

```bash
mysql -u root -p < sql/schema.sql
mysql -u root -p < sql/seed.sql
```

The running slice does not require MySQL yet. Point `DATABASE_URL` at it when the worker sync jobs are wired.

## What this slice does

1. `POST /api/recipe/generate` extracts intent, scores canonical recipes, hard-filters diet, computes nutrition and estimated cost, diffs pantry.
2. Shopping list is the missing quantities only.
3. Cooking mode is a step state machine. Vision labels move the step; frames are not stored.
4. Completing a meal writes a `food_events` row and prepends the dish to recent profile memory.

## Recipe import and reference projects

`/import` accepts user-pasted recipe text or JSON/JSON-LD. It parses a preview, lets the user edit the title, ingredients, amounts and steps, then saves a private recipe. It does not fetch URLs or scrape recipe sites. The imported recipe is held in process memory in this vertical slice, so it is lost on restart; `recipes.owner_user_id` defines the private ownership boundary for the database-backed version. Existing MySQL installations can apply `sql/migrations/001_recipe_owner.sql` once.

The import flow borrows the high-level ideas of [RecipeSage](https://github.com/julianpoy/RecipeSage)'s reviewable ingestion pipeline and [Waivy](https://github.com/justinsuo/waivy)'s single-source recipe model. It does not copy their code or recipe catalogs. RecipeSage's README reserves commercial use pending a separate license; Waivy has no repository license file, so its code is not treated as reusable. The app keeps its existing policy against recipe-site scraping.

Jev is used as a bounded decision layer, not as a recipe generator or persistence authority. In one optional request it classifies content, scores completeness and estimates whether a person should review it. CookAI applies its own validation and still requires an explicit human review before saving. Low confidence cannot trigger a save.

Do not scrape recipe sites into this database. Canonical dishes, USDA, Open Food Facts, Wikidata and licensed sets are the allowed inputs.
