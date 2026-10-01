"""Food memory. MySQL when reachable, otherwise an in-process store so the slice runs."""

from __future__ import annotations

import json
from copy import deepcopy

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def mysql_ok() -> bool:
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


SEED_INGREDIENTS = [
    {"id": 1, "canonical_name": "Chicken", "aliases": ["murgh"], "vegetarian": 0, "vegan": 0, "animal_derived": 1, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "not_allowed", "allergens": [], "nutrition_data": {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6}},
    {"id": 2, "canonical_name": "Paneer", "aliases": ["cottage cheese"], "vegetarian": 1, "vegan": 0, "animal_derived": 1, "contains_gluten": 0, "contains_dairy": 1, "jain_status": "allowed", "allergens": ["dairy"], "nutrition_data": {"calories": 265, "protein_g": 18, "carbs_g": 1.2, "fat_g": 20.8}},
    {"id": 3, "canonical_name": "Rice", "aliases": ["chawal"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}},
    {"id": 4, "canonical_name": "Tomato", "aliases": ["tamatar"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 18, "protein_g": 0.9, "carbs_g": 3.9, "fat_g": 0.2}},
    {"id": 5, "canonical_name": "Onion", "aliases": ["pyaaz"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "not_allowed", "allergens": [], "nutrition_data": {"calories": 40, "protein_g": 1.1, "carbs_g": 9.3, "fat_g": 0.1}},
    {"id": 6, "canonical_name": "Garlic", "aliases": ["lehsun"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "not_allowed", "allergens": [], "nutrition_data": {"calories": 149, "protein_g": 6.4, "carbs_g": 33, "fat_g": 0.5}},
    {"id": 7, "canonical_name": "Basil", "aliases": ["thai basil"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 23, "protein_g": 3.2, "carbs_g": 2.6, "fat_g": 0.6}},
    {"id": 8, "canonical_name": "Soy sauce", "aliases": [], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 1, "contains_dairy": 0, "jain_status": "not_allowed", "allergens": ["gluten", "soy"], "nutrition_data": {"calories": 53, "protein_g": 8, "carbs_g": 5, "fat_g": 0.1}},
    {"id": 9, "canonical_name": "Lentil", "aliases": ["dal"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 116, "protein_g": 9, "carbs_g": 20, "fat_g": 0.4}},
    {"id": 10, "canonical_name": "Mustard oil", "aliases": [], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 884, "protein_g": 0, "carbs_g": 0, "fat_g": 100}},
    {"id": 11, "canonical_name": "Wheat flour", "aliases": ["atta"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 1, "contains_dairy": 0, "jain_status": "allowed", "allergens": ["gluten"], "nutrition_data": {"calories": 340, "protein_g": 12, "carbs_g": 72, "fat_g": 1.7}},
    {"id": 12, "canonical_name": "Sattu", "aliases": [], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 390, "protein_g": 22, "carbs_g": 58, "fat_g": 6}},
    {"id": 13, "canonical_name": "Eggplant", "aliases": ["baingan"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 25, "protein_g": 1, "carbs_g": 6, "fat_g": 0.2}},
    {"id": 14, "canonical_name": "Potato", "aliases": ["aloo"], "vegetarian": 1, "vegan": 1, "animal_derived": 0, "contains_gluten": 0, "contains_dairy": 0, "jain_status": "allowed", "allergens": [], "nutrition_data": {"calories": 77, "protein_g": 2, "carbs_g": 17, "fat_g": 0.1}},
    {"id": 15, "canonical_name": "Butter", "aliases": [], "vegetarian": 1, "vegan": 0, "animal_derived": 1, "contains_gluten": 0, "contains_dairy": 1, "jain_status": "allowed", "allergens": ["dairy"], "nutrition_data": {"calories": 717, "protein_g": 0.9, "carbs_g": 0.1, "fat_g": 81}},
    {"id": 16, "canonical_name": "Yogurt", "aliases": ["dahi"], "vegetarian": 1, "vegan": 0, "animal_derived": 1, "contains_gluten": 0, "contains_dairy": 1, "jain_status": "allowed", "allergens": ["dairy"], "nutrition_data": {"calories": 61, "protein_g": 3.5, "carbs_g": 4.7, "fat_g": 3.3}},
]

SEED_RECIPES = [
    {
        "id": 1, "canonical_name": "Dal Tadka", "country": "India", "region": "North", "cuisine": "Indian",
        "difficulty": "easy", "prep_minutes": 10, "cook_minutes": 25,
        "ingredients": [
            {"name": "Lentil", "quantity": 200, "unit": "g"},
            {"name": "Tomato", "quantity": 150, "unit": "g"},
            {"name": "Onion", "quantity": 80, "unit": "g"},
            {"name": "Garlic", "quantity": 10, "unit": "g"},
            {"name": "Mustard oil", "quantity": 15, "unit": "ml"},
        ],
        "steps": [
            {"step": 1, "instruction": "Rinse lentils and simmer until soft.", "duration_seconds": 900},
            {"step": 2, "instruction": "Heat mustard oil, add onion, garlic and tomato.", "duration_seconds": 300},
            {"step": 3, "instruction": "Pour tadka over dal and simmer 2 minutes.", "duration_seconds": 120},
        ],
    },
    {
        "id": 2, "canonical_name": "Litti Chokha", "country": "India", "region": "Bihar / Jharkhand", "cuisine": "Eastern Indian",
        "difficulty": "medium", "prep_minutes": 20, "cook_minutes": 40,
        "ingredients": [
            {"name": "Wheat flour", "quantity": 200, "unit": "g"},
            {"name": "Sattu", "quantity": 120, "unit": "g"},
            {"name": "Mustard oil", "quantity": 20, "unit": "ml"},
            {"name": "Eggplant", "quantity": 250, "unit": "g"},
            {"name": "Tomato", "quantity": 150, "unit": "g"},
            {"name": "Potato", "quantity": 150, "unit": "g"},
        ],
        "steps": [
            {"step": 1, "instruction": "Knead wheat flour into a firm dough.", "duration_seconds": 300},
            {"step": 2, "instruction": "Mix sattu with mustard oil and salt.", "duration_seconds": 180},
            {"step": 3, "instruction": "Stuff and roast the littis until crusted.", "duration_seconds": 1200},
            {"step": 4, "instruction": "Mash roasted eggplant with tomato and potato.", "duration_seconds": 900},
        ],
    },
    {
        "id": 3, "canonical_name": "Thai Basil Chicken", "country": "Thailand", "region": "Central", "cuisine": "Thai",
        "difficulty": "easy", "prep_minutes": 10, "cook_minutes": 20,
        "ingredients": [
            {"name": "Chicken", "quantity": 500, "unit": "g"},
            {"name": "Basil", "quantity": 20, "unit": "g"},
            {"name": "Tomato", "quantity": 100, "unit": "g"},
            {"name": "Soy sauce", "quantity": 30, "unit": "ml"},
            {"name": "Rice", "quantity": 300, "unit": "g"},
            {"name": "Garlic", "quantity": 10, "unit": "g"},
        ],
        "steps": [
            {"step": 1, "instruction": "Heat oil until shimmering.", "duration_seconds": 60},
            {"step": 2, "instruction": "Add garlic, then chicken. Stir until no longer pink.", "duration_seconds": 360},
            {"step": 3, "instruction": "Add soy sauce and tomato. Cook until light golden.", "duration_seconds": 180},
            {"step": 4, "instruction": "Fold in basil off heat. Serve with rice.", "duration_seconds": 60},
        ],
    },
    {
        "id": 4, "canonical_name": "Paneer Butter Masala", "country": "India", "region": "North", "cuisine": "Indian",
        "difficulty": "easy", "prep_minutes": 15, "cook_minutes": 25,
        "ingredients": [
            {"name": "Paneer", "quantity": 300, "unit": "g"},
            {"name": "Tomato", "quantity": 300, "unit": "g"},
            {"name": "Butter", "quantity": 30, "unit": "g"},
            {"name": "Onion", "quantity": 100, "unit": "g"},
            {"name": "Yogurt", "quantity": 50, "unit": "g"},
        ],
        "steps": [
            {"step": 1, "instruction": "Blend tomato and spices into a gravy base.", "duration_seconds": 180},
            {"step": 2, "instruction": "Cook gravy in butter until oil separates.", "duration_seconds": 600},
            {"step": 3, "instruction": "Add paneer and a spoon of yogurt. Simmer gently.", "duration_seconds": 300},
        ],
    },
]


class Memory:
    def __init__(self):
        self.users = {1: {"id": 1, "name": "Shailendra", "currency": "INR", "country": "IN"}}
        self.households = {1: {"id": 1, "owner_user_id": 1, "name": "Shailendra Household"}}
        self.members = [
            {"id": 1, "household_id": 1, "name": "Shailendra", "diet_profile": "none", "allergies": [], "spice_level": 0.75},
            {"id": 2, "household_id": 1, "name": "Member", "diet_profile": "vegetarian", "allergies": [], "spice_level": 0.5},
        ]
        self.profiles = {
            1: {
                "user_id": 1,
                "favorite_cuisines": ["Indian", "Thai"],
                "recent_dishes": ["Paneer Butter Masala", "Chicken Biryani", "Dal Tadka"],
                "disliked_ingredients": ["raw_onion"],
                "spice_level": 0.75,
                "exploration_level": 0.72,
                "budget_preferences": {"meal_budget_inr": 280, "dinner_budget_inr": 700},
                "nutrition_targets": {"calories": 2000, "protein_g": 90},
                "recommendation_memory": {
                    "cuisines": {"Indian": 0.92, "Thai": 0.4, "Korean": 0.1},
                    "proteins": {"chicken": 0.83, "paneer": 0.71},
                    "newness_needed": 0.7,
                },
            }
        }
        self.ingredients = deepcopy(SEED_INGREDIENTS)
        self.recipes = deepcopy(SEED_RECIPES)
        self.pantry = [
            {"id": 1, "user_id": 1, "name": "Tomato", "ingredient_id": 4, "quantity": 300, "unit": "g"},
            {"id": 2, "user_id": 1, "name": "Rice", "ingredient_id": 3, "quantity": 400, "unit": "g"},
            {"id": 3, "user_id": 1, "name": "Soy sauce", "ingredient_id": 8, "quantity": 100, "unit": "ml"},
        ]
        self.events = []
        self.sessions = []
        self.lists = []
        self.usage = []
        self.pending_recipe_imports = {}
        self._ids = {"event": 1, "session": 1, "list": 1, "pantry": 4, "recipe": 5, "recipe_import": 1}

    def next_id(self, key: str) -> int:
        n = self._ids[key]
        self._ids[key] += 1
        return n


mem = Memory()


def loads(value):
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value
