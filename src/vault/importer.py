"""CSV importer for Collectr exports."""

import csv
from pathlib import Path
from typing import Generator

from . import database


# Collectr CSV columns
EXPECTED_COLUMNS = [
    "Portfolio Name", "Category", "Set", "Product Name", "Card Number",
    "Rarity", "Variance", "Grade", "Card Condition", "Average Cost Paid",
    "Quantity", "Market Price", "Price Override", "Watchlist", "Date Added", "Notes"
]


def parse_price(value: str) -> float | None:
    """Parse a price string like '$12.34' or '12.34' to float."""
    if not value or value.strip() == "":
        return None
    # Remove $ and any commas
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_quantity(value: str) -> int:
    """Parse quantity string to int, defaulting to 1."""
    if not value or value.strip() == "":
        return 1
    try:
        return int(value)
    except ValueError:
        return 1


def is_sealed_product(category: str, product_name: str) -> bool:
    """
    Determine if an item is sealed product (vs single card).
    Sealed products can't be auto-priced via the card API.
    """
    category_lower = (category or "").lower()
    name_lower = (product_name or "").lower()

    sealed_keywords = [
        "sealed", "booster", "box", "pack", "etb", "elite trainer",
        "collection", "tin", "bundle", "case", "display"
    ]

    if "sealed" in category_lower:
        return True

    for keyword in sealed_keywords:
        if keyword in name_lower:
            return True

    return False


def read_csv(filepath: Path) -> Generator[dict, None, None]:
    """Read a Collectr CSV and yield normalized row dicts."""
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Find the market price column (may have date suffix like "Market Price (As of 2025-12-18)")
        market_price_col = "Market Price"
        if reader.fieldnames:
            for col in reader.fieldnames:
                if col.startswith("Market Price"):
                    market_price_col = col
                    break

        for row in reader:
            yield {
                "portfolio_name": row.get("Portfolio Name", "").strip(),
                "category": row.get("Category", "").strip(),
                "set_name": row.get("Set", "").strip(),
                "name": row.get("Product Name", "").strip(),
                "card_number": row.get("Card Number", "").strip(),
                "rarity": row.get("Rarity", "").strip(),
                "variance": row.get("Variance", "").strip(),
                "grade": row.get("Grade", "").strip(),
                "condition": row.get("Card Condition", "").strip(),
                "cost_basis": parse_price(row.get("Average Cost Paid", "")),
                "quantity": parse_quantity(row.get("Quantity", "1")),
                "market_price": parse_price(row.get(market_price_col, "")),
                "price_override": parse_price(row.get("Price Override", "")),
                "date_added": row.get("Date Added", "").strip(),
                "notes": row.get("Notes", "").strip(),
            }


def import_csv(filepath: Path, progress_callback=None) -> dict:
    """
    Import items from a Collectr CSV file.
    Returns stats about the import.
    """
    database.init_db()

    stats = {
        "total": 0,
        "imported": 0,
        "updated": 0,
        "cards": 0,
        "sealed": 0,
        "errors": [],
    }

    rows = list(read_csv(filepath))
    stats["total"] = len(rows)

    for i, row in enumerate(rows):
        if progress_callback:
            progress_callback(i + 1, stats["total"], row["name"])

        if not row["name"]:
            stats["errors"].append(f"Row {i+1}: Missing product name")
            continue

        try:
            is_sealed = is_sealed_product(row["category"], row["name"])

            item_id = database.upsert_item(
                name=row["name"],
                set_name=row["set_name"] or None,
                card_number=row["card_number"] or None,
                rarity=row["rarity"] or None,
                variance=row["variance"] or None,
                quantity=row["quantity"],
                cost_basis=row["cost_basis"],
                is_sealed=is_sealed,
                portfolio_name=row["portfolio_name"] or None,
                grade=row["grade"] or None,
                condition=row["condition"] or None,
                notes=row["notes"] or None,
                date_added=row["date_added"] or None,
            )

            # Record initial price if we have one
            price = row["price_override"] or row["market_price"]
            if price and price > 0:
                database.record_price(item_id, price)

            stats["imported"] += 1
            if is_sealed:
                stats["sealed"] += 1
            else:
                stats["cards"] += 1

        except Exception as e:
            stats["errors"].append(f"Row {i+1} ({row['name']}): {str(e)}")

    return stats
