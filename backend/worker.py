from __future__ import annotations
import time
from datetime import datetime, timedelta, timezone
from config import JOB_INTERVALS
from fetch_openfoodfacts import main as sync_off
from fetch_usda import main as sync_usda
from fetch_wikidata import main as sync_wiki
from store import store


def recommendation_profile_update() -> None:
    """Fold recent behavior into profiles so scores reflect what people actually cook."""
    uid = 1  # slice: single demo household; iterate real users when multi-tenant
    profile = store.profile(uid)
    events = store.events(uid)
    cooked = [e for e in events if e.get("event_type") in {"COOKED", "MEAL"}]
    favorites = list(profile.get("favorite_cuisines") or [])
    for event in cooked[:10]:
        cuisine = ((event.get("data") or {}).get("cuisine") or "").strip()
        if cuisine and cuisine not in favorites:
            favorites.append(cuisine)
    recent_dishes = [((e.get("data") or {}).get("dish")) for e in cooked[:8]]
    store.save_profile(uid, {
        "favorite_cuisines": favorites[:6],
        "recent_dishes": [d for d in recent_dishes if d],
    })
    print(f"[worker] recommendation_profile_update: {len(cooked)} events folded")


def ai_usage_aggregation() -> None:
    """Roll raw ai_usage rows up per provider/task so cost is visible at a glance."""
    rows = store.usage_rows()
    totals: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        key = (str(row.get("provider") or "local"), str(row.get("task") or "unknown"))
        bucket = totals.setdefault(key, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        bucket["calls"] += 1
        bucket["tokens"] += int(row.get("input_tokens") or 0) + int(row.get("output_tokens") or 0)
        bucket["cost_usd"] += float(row.get("estimated_cost") or row.get("estimated_cost_usd") or 0)
    summary = [{"provider": p, "task": t, **v} for (p, t), v in sorted(totals.items())]
    print(f"[worker] ai_usage_aggregation: {sum(v['calls'] for v in totals.values())} calls, "
          f"${round(sum(v['cost_usd'] for v in totals.values()), 4)} estimated")
    # Aggregates are ephemeral by design; a metrics sink plugs in here later.
    store.remember_import(-1, {"ai_usage_summary": summary,
                               "at": datetime.now(timezone.utc).isoformat()})


def expired_media_deletion() -> None:
    """Delete media_assets rows past expires_at. Files live behind the storage seam."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=0)
    removed = 0
    try:
        from sqlalchemy import text

        from database import engine

        with engine().begin() as conn:
            result = conn.execute(
                text("DELETE FROM media_assets WHERE expires_at IS NOT NULL AND expires_at < NOW()"))
            removed = result.rowcount or 0
    except Exception as exc:
        # Memory store has no media table yet; nothing to expire.
        print(f"[worker] expired_media_deletion skipped ({store.kind} store): {exc}")
        return
    print(f"[worker] expired_media_deletion: removed {removed} rows before {cutoff.date()}")


JOBS = [
    ("usda_sync", JOB_INTERVALS["usda_sync"], sync_usda),
    ("open_food_facts_sync", JOB_INTERVALS["open_food_facts_sync"], sync_off),
    ("wikidata_enrichment", JOB_INTERVALS["wikidata_enrichment"], sync_wiki),
    ("recommendation_profile_update", JOB_INTERVALS["recommendation_profile_update"], recommendation_profile_update),
    ("ai_usage_aggregation", JOB_INTERVALS["ai_usage_aggregation"], ai_usage_aggregation),
    ("expired_media_deletion", JOB_INTERVALS["expired_media_deletion"], expired_media_deletion),
]


def run_once(name: str, fn) -> None:
    if fn is None:
        print(f"[worker] {name} not wired")
        return
    print(f"[worker] {name}")
    fn()


def main() -> None:
    last = {name: 0.0 for name, _, _ in JOBS}
    print(f"[worker] started with store={store.kind}")
    while True:
        now = time.time()
        for name, every, fn in JOBS:
            if now - last[name] >= every:
                try:
                    run_once(name, fn)
                except Exception as exc:
                    print(f"[worker] {name} failed: {exc}")
                last[name] = now
        time.sleep(JOB_INTERVALS.get("_tick", 30))


if __name__ == "__main__":
    main()
