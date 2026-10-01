"""Background jobs. One process, no Celery.

  python backend/worker.py
"""

from __future__ import annotations

import time

from fetch_openfoodfacts import main as sync_off
from fetch_usda import main as sync_usda
from fetch_wikidata import main as sync_wiki

JOBS = [
    ("usda_sync", 86400, sync_usda),
    ("open_food_facts_sync", 86400, sync_off),
    ("wikidata_enrichment", 86400, sync_wiki),
    ("recommendation_profile_update", 300, None),
    ("ai_usage_aggregation", 1800, None),
    ("expired_media_deletion", 21600, None),
]


def run_once(name: str, fn) -> None:
    if fn is None:
        print(f"[worker] {name} not wired")
        return
    print(f"[worker] {name}")
    fn()


def main() -> None:
    last = {name: 0.0 for name, _, _ in JOBS}
    print("[worker] started")
    while True:
        now = time.time()
        for name, every, fn in JOBS:
            if now - last[name] >= every:
                try:
                    run_once(name, fn)
                except Exception as exc:
                    print(f"[worker] {name} failed: {exc}")
                last[name] = now
        time.sleep(30)


if __name__ == "__main__":
    main()
