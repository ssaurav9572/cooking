from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import text

from config import STORE_BACKEND
from database import SEED_INGREDIENTS, SEED_RECIPES, loads, mem, mysql_ok

_TABLES = [
    "users", "households", "household_members", "profiles", "ingredients",
    "recipes", "pantry", "food_events", "conversations", "cooking_sessions",
    "shopping_lists", "merchants", "merchant_offers", "media_assets", "ai_usage",
]


class MemoryStore:
    """Wraps the in-process dict store. Everything stays volatile."""

    kind = "memory"

    def recipes(self, uid: int) -> list[dict]:
        return [r for r in mem.recipes if r.get("owner_user_id") in (None, uid)]

    def all_recipes(self) -> list[dict]:
        return list(mem.recipes)

    def get_recipe(self, recipe_id: int) -> dict | None:
        return next((r for r in mem.recipes if r.get("id") == recipe_id), None)

    def insert_recipe(self, recipe: dict) -> dict:
        row = deepcopy(recipe)
        row["id"] = mem.next_id("recipe")
        mem.recipes.append(row)
        return row

    def ingredients(self) -> list[dict]:
        return list(mem.ingredients)

    def pantry(self, uid: int) -> list[dict]:
        return [p for p in mem.pantry if p["user_id"] == uid]

    def add_pantry(self, row: dict) -> dict:
        out = deepcopy(row)
        out["id"] = mem.next_id("pantry")
        mem.pantry.append(out)
        return out

    def profile(self, uid: int) -> dict:
        return mem.profiles.setdefault(uid, {"user_id": uid})

    def save_profile(self, uid: int, patch: dict) -> dict:
        mem.profiles.setdefault(uid, {"user_id": uid}).update(patch)
        return mem.profiles[uid]

    def household_members(self, household_id: int) -> list[dict]:
        return [m for m in mem.members if m["household_id"] == household_id]

    def log_event(self, event: dict) -> dict:
        out = deepcopy(event)
        out["id"] = mem.next_id("event")
        mem.events.insert(0, out)
        return out

    def events(self, uid: int) -> list[dict]:
        return [e for e in mem.events if e["user_id"] == uid]

    def create_session(self, session: dict) -> dict:
        out = deepcopy(session)
        out["id"] = mem.next_id("session")
        mem.sessions.append(out)
        return out

    def get_session(self, session_id: int) -> dict | None:
        return next((s for s in mem.sessions if s["id"] == session_id), None)

    def update_session(self, session_id: int, patch: dict) -> dict | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        session.update(deepcopy(patch))
        return session

    def active_session_for_user(self, uid: int) -> dict | None:
        return next((s for s in reversed(mem.sessions) if s["user_id"] == uid and s.get("status") == "active"), None)

    def sessions(self) -> list[dict]:
        return list(mem.sessions)

    def add_list(self, shop: dict) -> dict:
        out = deepcopy(shop)
        out["id"] = mem.next_id("list")
        mem.lists.append(out)
        return out

    def get_list(self, list_id: int) -> dict | None:
        return next((s for s in mem.lists if s["id"] == list_id), None)

    def update_list(self, list_id: int, patch: dict) -> dict | None:
        shop = self.get_list(list_id)
        if shop is None:
            return None
        shop.update(patch)
        return shop

    def record_usage(self, row: dict) -> dict:
        mem.usage.append(deepcopy(row))
        return row

    def usage_rows(self) -> list[dict]:
        return list(mem.usage)

    def pending_import(self, preview_id: int) -> dict | None:
        return mem.pending_recipe_imports.get(preview_id)

    def remember_import(self, preview_id: int, payload: dict) -> None:
        mem.pending_recipe_imports[preview_id] = payload
        while len(mem.pending_recipe_imports) > 32:
            mem.pending_recipe_imports.pop(next(iter(mem.pending_recipe_imports)))

    def forget_import(self, preview_id: int) -> None:
        mem.pending_recipe_imports.pop(preview_id, None)

    def next_preview_id(self) -> int:
        return mem.next_id("recipe_import")

    def user(self, uid: int) -> dict:
        return mem.users.get(uid, {"id": uid, "name": f"user {uid}", "currency": "INR", "country": "IN", "language": "en"})

    def seed_if_empty(self) -> None:
        # The memory store boots pre-seeded by design.
        return None


_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe identifier: {name}")
    return name


class MySQLStore:
    """SQLAlchemy Core against the real schema. JSON columns via json.dumps/loads."""

    kind = "mysql"

    def __init__(self):
        from database import engine

        self._engine = engine()

    # -- helpers -----------------------------------------------------------
    def _fetchall(self, sql: str, params: dict | None = None) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]

    def _fetchone(self, sql: str, params: dict | None = None) -> dict | None:
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    def _execute(self, sql: str, params: dict | None = None):
        with self._engine.begin() as conn:
            return conn.execute(text(sql), params or {})

    def _insert(self, table: str, row: dict) -> int:
        cols = [_ident(c) for c in row]
        sql = f"INSERT INTO {_ident(table)} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"
        return int(self._execute(sql, row).lastrowid)

    def _hydrate_recipe(self, row: dict) -> dict:
        return {
            "id": row["id"], "owner_user_id": row.get("owner_user_id"),
            "canonical_name": row["canonical_name"], "country": row.get("country"),
            "region": row.get("region"), "cuisine": row.get("cuisine"),
            "difficulty": row.get("difficulty"), "servings": row.get("servings") or 2,
            "prep_minutes": row.get("prep_minutes") or 0, "cook_minutes": row.get("cook_minutes") or 0,
            "source_type": row.get("source_type") or "canonical",
            "confidence": float(row.get("confidence") or 0.8),
            "ingredients": loads(row.get("ingredients_json")) or [],
            "steps": loads(row.get("steps_json")) or [],
        }

    def _recipe_row(self, recipe: dict) -> dict:
        return {
            "owner_user_id": recipe.get("owner_user_id"),
            "canonical_name": recipe.get("canonical_name") or recipe.get("title") or "Untitled",
            "country": recipe.get("country"), "region": recipe.get("region"),
            "cuisine": recipe.get("cuisine"), "difficulty": recipe.get("difficulty") or "easy",
            "servings": int(recipe.get("servings") or 2),
            "prep_minutes": int(recipe.get("prep_minutes") or 0),
            "cook_minutes": int(recipe.get("cook_minutes") or 0),
            "source_type": recipe.get("source_type") or "canonical",
            "confidence": float(recipe.get("confidence") or 0.8),
            "ingredients_json": json.dumps(recipe.get("ingredients") or []),
            "steps_json": json.dumps(recipe.get("steps") or []),
        }

    # -- recipes -----------------------------------------------------------
    def all_recipes(self) -> list[dict]:
        return [self._hydrate_recipe(r) for r in self._fetchall("SELECT * FROM recipes")]

    def recipes(self, uid: int) -> list[dict]:
        return [self._hydrate_recipe(r) for r in self._fetchall(
            "SELECT * FROM recipes WHERE owner_user_id IS NULL OR owner_user_id = :uid", {"uid": uid})]

    def get_recipe(self, recipe_id: int) -> dict | None:
        row = self._fetchone("SELECT * FROM recipes WHERE id = :i", {"i": recipe_id})
        return self._hydrate_recipe(row) if row else None

    def insert_recipe(self, recipe: dict) -> dict:
        out = deepcopy(recipe)
        out["id"] = self._insert("recipes", self._recipe_row(recipe))
        return out

    # -- ingredients -------------------------------------------------------
    def ingredients(self) -> list[dict]:
        rows = self._fetchall("SELECT * FROM ingredients")
        for r in rows:
            r["aliases"] = loads(r.get("aliases")) or []
            r["allergens"] = loads(r.get("allergens")) or []
            r["nutrition_data"] = loads(r.get("nutrition_data")) or {}
        return rows

    # -- pantry ------------------------------------------------------------
    def pantry(self, uid: int) -> list[dict]:
        rows = self._fetchall("SELECT * FROM pantry WHERE user_id = :u", {"u": uid})
        names = {i["id"]: i["canonical_name"] for i in self.ingredients()}
        for r in rows:
            r["name"] = names.get(r["ingredient_id"], f"ingredient {r['ingredient_id']}")
            r["quantity"] = float(r.get("quantity") or 0)
        return rows

    def add_pantry(self, row: dict) -> dict:
        ingredient_id = row.get("ingredient_id")
        if ingredient_id is None:
            match = self._fetchone(
                "SELECT id FROM ingredients WHERE canonical_name = :n", {"n": row["name"]})
            ingredient_id = match["id"] if match else None
        if ingredient_id is None:
            raise ValueError(f"'{row['name']}' is not in the ingredient catalog; add it before stocking the pantry.")
        payload = {"user_id": row["user_id"], "ingredient_id": ingredient_id,
                   "quantity": float(row.get("quantity") or 0), "unit": row.get("unit") or "g"}
        out = deepcopy(row)
        out["id"] = self._insert("pantry", payload)
        out["ingredient_id"] = ingredient_id
        return out

    # -- profiles / members --------------------------------------------------
    def profile(self, uid: int) -> dict:
        row = self._fetchone("SELECT * FROM profiles WHERE user_id = :u", {"u": uid})
        if not row:
            return {"user_id": uid}
        for key in ("favorite_cuisines", "recent_dishes", "disliked_ingredients", "nutrition_targets",
                    "budget_preferences", "recommendation_memory"):
            row[key] = loads(row.get(key)) or []
        return row

    def save_profile(self, uid: int, patch: dict) -> dict:
        current = self.profile(uid)
        current.update(patch)
        json_keys = ["favorite_cuisines", "favorite_dishes", "liked_ingredients", "disliked_ingredients",
                     "frequent_dishes", "recent_dishes", "nutrition_targets", "budget_preferences",
                     "recommendation_memory", "equipment", "food_preferences"]
        row = {"user_id": uid}
        for key in json_keys:
            if key in current:
                row[key] = json.dumps(current.get(key) or [])
        for key in ("spice_level", "exploration_level"):
            if key in current:
                row[key] = float(current.get(key) or 0)
        cols = [_ident(c) for c in row]
        updates = ", ".join(f"{c} = :{c}" for c in cols if c != "user_id")
        self._execute(
            f"INSERT INTO profiles ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)}) "
            f"ON DUPLICATE KEY UPDATE {updates}", row)
        return self.profile(uid)

    def household_members(self, household_id: int) -> list[dict]:
        rows = self._fetchall("SELECT * FROM household_members WHERE household_id = :h", {"h": household_id})
        for r in rows:
            r["allergies"] = loads(r.get("allergies")) or []
            r["preferences"] = loads(r.get("preferences")) or {}
        return rows

    def user(self, uid: int) -> dict:
        row = self._fetchone("SELECT * FROM users WHERE id = :u", {"u": uid})
        return row or {"id": uid, "name": f"user {uid}", "currency": "INR", "country": "IN", "language": "en"}

    # -- events --------------------------------------------------------------
    def log_event(self, event: dict) -> dict:
        payload = {
            "user_id": event["user_id"], "event_type": event.get("event_type") or "COOKED",
            "reference_id": event.get("reference_id"), "calories": event.get("calories"),
            "protein_g": event.get("protein_g"), "carbs_g": event.get("carbs_g"),
            "fat_g": event.get("fat_g"), "amount": event.get("amount"),
            "currency": event.get("currency"), "data_json": json.dumps(event.get("data") or {}),
        }
        out = deepcopy(event)
        out["id"] = self._insert("food_events", payload)
        return out

    def events(self, uid: int) -> list[dict]:
        rows = self._fetchall(
            "SELECT * FROM food_events WHERE user_id = :u ORDER BY occurred_at DESC LIMIT 200", {"u": uid})
        for r in rows:
            r["data"] = loads(r.get("data_json")) or {}
            r["calories"] = float(r["calories"]) if r.get("calories") is not None else None
            r["protein_g"] = float(r["protein_g"]) if r.get("protein_g") is not None else None
        return rows

    # -- cooking sessions ------------------------------------------------------
    def create_session(self, session: dict) -> dict:
        payload = {
            "user_id": session["user_id"], "recipe_id": session["recipe_id"],
            "current_step": int(session.get("current_step") or 1),
            "status": session.get("status") or "active",
            "state_json": json.dumps({
                "steps": session.get("steps") or [], "title": session.get("title"),
                "state": session.get("state") or {}, "timeline": session.get("timeline") or [],
            }),
        }
        out = deepcopy(session)
        out["id"] = self._insert("cooking_sessions", payload)
        return out

    def get_session(self, session_id: int) -> dict | None:
        row = self._fetchone("SELECT * FROM cooking_sessions WHERE id = :i", {"i": session_id})
        if not row:
            return None
        blob = loads(row.get("state_json")) or {}
        return {
            "id": row["id"], "user_id": row["user_id"], "recipe_id": row["recipe_id"],
            "current_step": row["current_step"], "status": row["status"],
            "started_at": str(row.get("started_at")), "completed_at": str(row.get("completed_at") or ""),
            "title": blob.get("title"), "steps": blob.get("steps") or [],
            "state": blob.get("state") or {}, "timeline": blob.get("timeline") or [],
        }

    def update_session(self, session_id: int, patch: dict) -> dict | None:
        existing = self.get_session(session_id)
        if existing is None:
            return None
        merged = {**existing, **patch}
        payload = {
            "current_step": int(merged.get("current_step") or 1),
            "status": merged.get("status") or "active",
            "state_json": json.dumps({
                "steps": merged.get("steps") or [], "title": merged.get("title"),
                "state": merged.get("state") or {}, "timeline": merged.get("timeline") or [],
            }),
        }
        if merged.get("status") == "completed":
            payload["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cols = ", ".join(f"{_ident(c)} = :{c}" for c in payload)
        self._execute(f"UPDATE cooking_sessions SET {cols} WHERE id = :sid", {**payload, "sid": session_id})
        return self.get_session(session_id)

    def active_session_for_user(self, uid: int) -> dict | None:
        row = self._fetchone(
            "SELECT id FROM cooking_sessions WHERE user_id = :u AND status = 'active' ORDER BY id DESC LIMIT 1",
            {"u": uid})
        return self.get_session(row["id"]) if row else None

    def sessions(self) -> list[dict]:
        rows = self._fetchall("SELECT id FROM cooking_sessions ORDER BY id")
        return [s for s in (self.get_session(r["id"]) for r in rows) if s]

    # -- shopping lists ----------------------------------------------------------
    def add_list(self, shop: dict) -> dict:
        payload = {"user_id": shop["user_id"], "recipe_id": shop.get("recipe_id"),
                   "items_json": json.dumps(shop.get("items") or []), "status": shop.get("status") or "open"}
        out = deepcopy(shop)
        out["id"] = self._insert("shopping_lists", payload)
        return out

    def get_list(self, list_id: int) -> dict | None:
        row = self._fetchone("SELECT * FROM shopping_lists WHERE id = :i", {"i": list_id})
        if not row:
            return None
        row["items"] = loads(row.get("items_json")) or []
        return row

    def update_list(self, list_id: int, patch: dict) -> dict | None:
        payload = {}
        if "status" in patch:
            payload["status"] = patch["status"]
        if "actual_total" in patch:
            payload["actual_total"] = patch["actual_total"]
        if "items" in patch:
            payload["items_json"] = json.dumps(patch["items"])
        if payload:
            cols = ", ".join(f"{_ident(c)} = :{c}" for c in payload)
            self._execute(f"UPDATE shopping_lists SET {cols} WHERE id = :sid", {**payload, "sid": list_id})
        return self.get_list(list_id)

    # -- ai usage ------------------------------------------------------------------
    def record_usage(self, row: dict) -> dict:
        self._insert("ai_usage", {
            "user_id": row.get("user_id"), "provider": row.get("provider") or "local",
            "model": row.get("model") or "unknown", "task": row.get("task") or "unknown",
            "input_tokens": int(row.get("input_tokens") or 0), "output_tokens": int(row.get("output_tokens") or 0),
            "duration_ms": int(row.get("duration_ms") or 0), "estimated_cost": float(row.get("estimated_cost_usd") or 0),
        })
        return row

    def usage_rows(self) -> list[dict]:
        return self._fetchall("SELECT * FROM ai_usage ORDER BY id DESC LIMIT 5000")

    # -- pending imports (ephemeral even with MySQL) ---------------------------------
    def pending_import(self, preview_id: int) -> dict | None:
        return mem.pending_recipe_imports.get(preview_id)

    def remember_import(self, preview_id: int, payload: dict) -> None:
        mem.pending_recipe_imports[preview_id] = payload
        while len(mem.pending_recipe_imports) > 32:
            mem.pending_recipe_imports.pop(next(iter(mem.pending_recipe_imports)))

    def forget_import(self, preview_id: int) -> None:
        mem.pending_recipe_imports.pop(preview_id, None)

    def next_preview_id(self) -> int:
        return mem.next_id("recipe_import")

    # -- first-run seeding -------------------------------------------------------------
    def seed_if_empty(self) -> None:
        row = self._fetchone("SELECT COUNT(*) AS n FROM ingredients")
        if row and row["n"]:
            return
        with self._engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in reversed(_TABLES):
                conn.execute(text(f"TRUNCATE TABLE {_ident(table)}"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        self._insert("users", {"id": 1, "email": "demo@cookai.local", "password_hash": "! unusable demo hash !",
                               "name": "Shailendra", "country": "IN", "language": "en", "currency": "INR"})
        self._insert("households", {"id": 1, "owner_user_id": 1, "name": "Shailendra Household",
                                    "country": "IN", "currency": "INR"})
        for member in mem.members:
            self._insert("household_members", {
                "household_id": member["household_id"], "name": member["name"],
                "diet_profile": member.get("diet_profile") or "none",
                "allergies": json.dumps(member.get("allergies") or []),
                "spice_level": float(member.get("spice_level") or 0.5)})
        profile = mem.profiles[1]
        self.save_profile(1, profile)
        for ing in SEED_INGREDIENTS:
            self._insert("ingredients", {
                "id": ing["id"], "canonical_name": ing["canonical_name"],
                "aliases": json.dumps(ing.get("aliases") or []),
                "vegetarian": int(ing.get("vegetarian") or 0), "vegan": int(ing.get("vegan") or 0),
                "animal_derived": int(ing.get("animal_derived") or 0),
                "contains_gluten": int(ing.get("contains_gluten") or 0),
                "contains_dairy": int(ing.get("contains_dairy") or 0),
                "jain_status": ing.get("jain_status") or "unknown",
                "allergens": json.dumps(ing.get("allergens") or []),
                "nutrition_data": json.dumps(ing.get("nutrition_data") or {}), "source": "seed"})
        for recipe in SEED_RECIPES:
            self._insert("recipes", self._recipe_row({**recipe, "owner_user_id": None}))
        for item in mem.pantry:
            self._insert("pantry", {"user_id": item["user_id"], "ingredient_id": item["ingredient_id"],
                                    "quantity": float(item["quantity"]), "unit": item["unit"]})


def build_store():
    backend = STORE_BACKEND
    if backend == "auto":
        backend = "mysql" if mysql_ok() else "memory"
    if backend == "mysql":
        store = MySQLStore()
        store.seed_if_empty()
        return store
    if backend == "memory":
        return MemoryStore()
    raise RuntimeError(f"Unknown STORE_BACKEND '{STORE_BACKEND}'. Use memory, mysql, or auto.")


store = build_store()
