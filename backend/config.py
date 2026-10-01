import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def _csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://cookai:cookai@127.0.0.1:3306/cookai",
)
# memory | mysql | auto  (auto = MySQL when reachable, otherwise the volatile store)
STORE_BACKEND = os.getenv("STORE_BACKEND", "auto").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
JEV_API_KEY = os.getenv("JEV_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# CORS is a deployment decision, never a wildcard by default in production.
APP_ENV = os.getenv("APP_ENV", "development")
CORS_ORIGINS = _csv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000" if APP_ENV != "production" else "")

# Auth: dev keeps the X-User-Id header; production requires signed tokens.
AUTH_MODE = os.getenv("AUTH_MODE", "header" if APP_ENV != "production" else "jwt")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "43200"))  # 30 days: mobile sessions survive app switches

# Vision loop policy: how confident must the model be before the engine acts on it.
VISION_MIN_CONFIDENCE = float(os.getenv("VISION_MIN_CONFIDENCE", "0.6"))
VISION_ADVANCE_STATES = set(_csv("VISION_ADVANCE_STATES", "done,light_golden,correct,golden"))
VISION_RESCUE_STATES = set(_csv("VISION_RESCUE_STATES", "burning,smoking,charred"))
VISION_HOLD_STATES = set(_csv("VISION_HOLD_STATES", "raw,incomplete,undercooked,soggy"))

# Language support is data-driven: add codes here (or via profile.language) and the app follows.
SUPPORTED_LANGUAGES = _csv("SUPPORTED_LANGUAGES", "en,hi,bn,ta,te,mr,ur")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")

# AI usage accounting.
AI_USAGE_ENABLED = _flag("AI_USAGE_ENABLED", "true")
AI_PRICE_PER_MTOK_IN_USD = os.getenv("AI_PRICE_PER_MTOK_IN_USD", "")  # optional override, e.g. "gemini:0.3/2.5"

# Worker cadence in seconds (overridable per job).
WORKER_INTERVAL_SECONDS = int(os.getenv("WORKER_INTERVAL_SECONDS", "30"))
JOB_INTERVALS = {
    "usda_sync": int(os.getenv("JOB_EVERY_USDA_SYNC", "86400")),
    "open_food_facts_sync": int(os.getenv("JOB_EVERY_OPEN_FOOD_FACTS_SYNC", "86400")),
    "wikidata_enrichment": int(os.getenv("JOB_EVERY_WIKIDATA_ENRICHMENT", "86400")),
    "recommendation_profile_update": int(os.getenv("JOB_EVERY_RECOMMENDATION_PROFILE_UPDATE", "300")),
    "ai_usage_aggregation": int(os.getenv("JOB_EVERY_AI_USAGE_AGGREGATION", "1800")),
    "expired_media_deletion": int(os.getenv("JOB_EVERY_EXPIRED_MEDIA_DELETION", "21600")),
}
