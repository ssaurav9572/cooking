"""Table names live in sql/schema.sql. The slice reads the in-process memory in database.py.

When MySQL is connected, map these names 1:1:
users, households, household_members, profiles, ingredients, recipes,
pantry, food_events, conversations, cooking_sessions, shopping_lists,
merchants, merchant_offers, media_assets, ai_usage.
"""

TABLES = [
    "users",
    "households",
    "household_members",
    "profiles",
    "ingredients",
    "recipes",
    "pantry",
    "food_events",
    "conversations",
    "cooking_sessions",
    "shopping_lists",
    "merchants",
    "merchant_offers",
    "media_assets",
    "ai_usage",
]
