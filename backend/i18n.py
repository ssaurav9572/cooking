from __future__ import annotations

import json
import re
from pathlib import Path

from config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

LOCALE_DIR = Path(__file__).resolve().parent / "locales"
_TOKEN = re.compile(r"\{(\w+)\}")

_catalogs: dict[str, dict[str, str]] = {}


def _load() -> dict[str, dict[str, str]]:
    global _catalogs
    if _catalogs:
        return _catalogs
    for path in sorted(LOCALE_DIR.glob("*.json")):
        code = path.stem.lower()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            _catalogs[code] = {k: str(v) for k, v in data.items()}
    return _catalogs


def available_languages() -> list[str]:
    codes = set(_load()) | set(SUPPORTED_LANGUAGES)
    ordered = [c for c in SUPPORTED_LANGUAGES if c in codes]
    extras = sorted(codes - set(ordered))
    return ordered + extras


def normalize_language(code: str | None) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    base = code.strip().lower().split("-")[0]
    langs = available_languages()
    if base in langs:
        return base
    return DEFAULT_LANGUAGE


def detect_language(text: str) -> str | None:
    """Script-based detection: Devanagari -> hi, Bengali -> bn, Tamil -> ta, Telugu -> te.

    Latin script returns None (fall through to the user's profile language).
    """
    sample = text or ""
    checks = [
        ("hi", r"[\u0900-\u097F]"),   # Devanagari
        ("bn", r"[\u0980-\u09FF]"),   # Bengali
        ("ta", r"[\u0B80-\u0BFF]"),   # Tamil
        ("te", r"[\u0C00-\u0C7F]"),   # Telugu
        ("ur", r"[\u0600-\u06FF]"),   # Arabic/Urdu block
    ]
    for code, pattern in checks:
        if re.search(pattern, sample) and code in available_languages():
            return code
    return None


def t(key: str, params: dict | None = None, language: str | None = None) -> str:
    """Translate with fallback chain: requested -> default -> key itself."""
    catalogs = _load()
    lang = normalize_language(language)
    for code in (lang, DEFAULT_LANGUAGE):
        template = catalogs.get(code, {}).get(key)
        if template is not None:
            out = template
            for name, value in (params or {}).items():
                out = out.replace("{%s}" % name, str(value))
            return out
    return key
