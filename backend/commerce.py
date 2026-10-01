"""Commerce adapters stay in one file until a provider is real."""

from __future__ import annotations


class Commerce:
    def search_products(self, items: list[dict], city: str = "Dhanbad") -> list[dict]:
        offers = []
        for item in items:
            name = item.get("name")
            qty = item.get("quantity")
            offers.append({
                "product_name": f"{name} {qty}{item.get('unit') or ''}",
                "merchant": "Local Grocery",
                "city": city,
                "price": None,
                "currency": "INR",
                "sponsored": False,
                "delivery_available": False,
                "note": "Estimate only until a merchant API is connected.",
            })
        return offers

    def rank(self, offers: list[dict]) -> list[dict]:
        # Relevance and availability outrank bid. Sponsored must stay labelled.
        def key(o):
            return (
                0 if o.get("stock_status") == "in_stock" else 1,
                0 if not o.get("sponsored") else 1,
                -(o.get("bid_amount") or 0),
            )
        ranked = sorted(offers, key=key)
        for o in ranked:
            if o.get("sponsored"):
                o["label"] = "Sponsored"
        return ranked


commerce = Commerce()
