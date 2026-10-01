"""Run the allowed intelligence imports. No recipe-site scraping.

  python backend/fetch_all.py
"""

from fetch_openfoodfacts import main as off
from fetch_usda import main as usda
from fetch_wikidata import main as wiki


def main() -> None:
    usda()
    off()
    wiki()


if __name__ == "__main__":
    main()
