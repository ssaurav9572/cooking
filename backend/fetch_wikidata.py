"""Pull dish/ingredient ontology from Wikidata. Not recipe instructions.

  python backend/fetch_wikidata.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = """
SELECT ?item ?itemLabel ?countryLabel ?cuisineLabel ?alias WHERE {
  ?item wdt:P31/wdt:P279* wd:Q746549 .
  OPTIONAL { ?item wdt:P495 ?country. }
  OPTIONAL { ?item wdt:P2012 ?cuisine. }
  OPTIONAL { ?item skos:altLabel ?alias FILTER (LANG(?alias) IN ("en","hi")) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hi". }
}
LIMIT 500
"""


def main() -> None:
    agent = os.getenv("WIKIDATA_USER_AGENT", "CookAI/0.1 (local)")
    out_dir = ROOT / os.getenv("DATA_DIR", "data")
    out_dir.mkdir(parents=True, exist_ok=True)
    response = httpx.get(
        ENDPOINT,
        params={"query": QUERY, "format": "json"},
        headers={"User-Agent": agent, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    response.raise_for_status()
    grouped: dict[str, dict] = {}
    for row in response.json()["results"]["bindings"]:
        qid = row["item"]["value"].rsplit("/", 1)[-1]
        item = grouped.setdefault(qid, {
            "source_id": qid,
            "canonical_name": row.get("itemLabel", {}).get("value"),
            "country": None,
            "cuisine": None,
            "aliases": [],
            "source": "wikidata",
            "license": "CC0",
        })
        item["country"] = item["country"] or row.get("countryLabel", {}).get("value")
        item["cuisine"] = item["cuisine"] or row.get("cuisineLabel", {}).get("value")
        alias = row.get("alias", {}).get("value")
        if alias and alias not in item["aliases"] and alias != item["canonical_name"]:
            item["aliases"].append(alias)
    path = out_dir / "wikidata_dishes.json"
    path.write_text(json.dumps(list(grouped.values()), indent=2))
    print(f"wrote {len(grouped)} dishes to {path}")


if __name__ == "__main__":
    main()
