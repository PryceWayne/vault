"""Database module for Vault."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_db_path() -> Path:
    """Get the database file path."""
    # Use environment variable if set, otherwise use home directory
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        # On Railway, use /tmp which is always writable
        vault_dir = Path('/tmp')
    else:
        # Local development
        vault_dir = Path.home() / '.vault'
        vault_dir.mkdir(exist_ok=True)
    return vault_dir / 'vault.db'


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            set_name TEXT,
            card_number TEXT,
            rarity TEXT,
            variance TEXT,
            quantity INTEGER DEFAULT 1,
            cost_basis REAL,
            is_sealed INTEGER DEFAULT 0,
            api_id TEXT,
            portfolio_name TEXT,
            grade TEXT,
            condition TEXT,
            notes TEXT,
            date_added TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, set_name, card_number, variance, grade, condition)
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            threshold_pct REAL NOT NULL,
            direction TEXT CHECK(direction IN ('up', 'down', 'both')) DEFAULT 'both',
            triggered_at TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_prices_item_id ON prices(item_id);
        CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON prices(timestamp);
        CREATE INDEX IF NOT EXISTS idx_items_api_id ON items(api_id);
    """)

    conn.commit()
    conn.close()


def upsert_item(
    name: str,
    set_name: Optional[str] = None,
    card_number: Optional[str] = None,
    rarity: Optional[str] = None,
    variance: Optional[str] = None,
    quantity: int = 1,
    cost_basis: Optional[float] = None,
    is_sealed: bool = False,
    api_id: Optional[str] = None,
    portfolio_name: Optional[str] = None,
    grade: Optional[str] = None,
    condition: Optional[str] = None,
    notes: Optional[str] = None,
    date_added: Optional[str] = None,
) -> int:
    """Insert or update an item, returning the item ID."""
    conn = get_connection()
    cursor = conn.cursor()

    # Try to find existing item
    cursor.execute("""
        SELECT id FROM items
        WHERE name = ? AND set_name IS ? AND card_number IS ?
        AND variance IS ? AND grade IS ? AND condition IS ?
    """, (name, set_name, card_number, variance, grade, condition))

    row = cursor.fetchone()

    if row:
        item_id = row["id"]
        cursor.execute("""
            UPDATE items SET
                rarity = ?,
                quantity = ?,
                cost_basis = ?,
                is_sealed = ?,
                api_id = COALESCE(?, api_id),
                portfolio_name = ?,
                notes = ?,
                date_added = ?,
                updated_at = ?
            WHERE id = ?
        """, (rarity, quantity, cost_basis, int(is_sealed), api_id,
              portfolio_name, notes, date_added, datetime.now().isoformat(), item_id))
    else:
        cursor.execute("""
            INSERT INTO items (
                name, set_name, card_number, rarity, variance, quantity,
                cost_basis, is_sealed, api_id, portfolio_name, grade,
                condition, notes, date_added
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, set_name, card_number, rarity, variance, quantity,
              cost_basis, int(is_sealed), api_id, portfolio_name, grade,
              condition, notes, date_added))
        item_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return item_id


def record_price(item_id: int, price: float) -> None:
    """Record a price snapshot for an item."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO prices (item_id, price) VALUES (?, ?)",
        (item_id, price)
    )
    conn.commit()
    conn.close()


def get_all_items() -> list[dict]:
    """Get all items with their latest prices."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            i.*,
            p1.price as current_price,
            p1.timestamp as price_timestamp,
            p2.price as previous_price
        FROM items i
        LEFT JOIN prices p1 ON i.id = p1.item_id
            AND p1.timestamp = (
                SELECT MAX(timestamp) FROM prices WHERE item_id = i.id
            )
        LEFT JOIN prices p2 ON i.id = p2.item_id
            AND p2.timestamp = (
                SELECT MAX(timestamp) FROM prices
                WHERE item_id = i.id AND timestamp < p1.timestamp
            )
        ORDER BY i.name
    """)

    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def get_item_by_id(item_id: int) -> Optional[dict]:
    """Get a single item by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_price_history(item_id: int, limit: int = 30) -> list[dict]:
    """Get price history for an item."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT price, timestamp
        FROM prices
        WHERE item_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (item_id, limit))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


def get_items_needing_update() -> list[dict]:
    """Get cards (non-sealed) that can be auto-priced via API."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM items
        WHERE is_sealed = 0
        ORDER BY updated_at ASC
    """)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def get_summary_stats() -> dict:
    """Get portfolio summary statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total items and quantities
    cursor.execute("""
        SELECT
            COUNT(*) as item_count,
            SUM(quantity) as total_quantity,
            SUM(CASE WHEN is_sealed = 1 THEN 1 ELSE 0 END) as sealed_count,
            SUM(CASE WHEN is_sealed = 0 THEN 1 ELSE 0 END) as card_count
        FROM items
    """)
    counts = dict(cursor.fetchone())

    # Current total value
    cursor.execute("""
        SELECT SUM(i.quantity * p.price) as total_value
        FROM items i
        JOIN prices p ON i.id = p.item_id
        WHERE p.timestamp = (
            SELECT MAX(timestamp) FROM prices WHERE item_id = i.id
        )
    """)
    row = cursor.fetchone()
    total_value = row["total_value"] if row["total_value"] else 0

    # Total cost basis
    cursor.execute("SELECT SUM(quantity * cost_basis) as total_cost FROM items WHERE cost_basis IS NOT NULL")
    row = cursor.fetchone()
    total_cost = row["total_cost"] if row["total_cost"] else 0

    # Previous day value (prices from ~24 hours ago)
    cursor.execute("""
        SELECT SUM(i.quantity * p.price) as prev_value
        FROM items i
        JOIN prices p ON i.id = p.item_id
        WHERE p.timestamp = (
            SELECT MAX(timestamp) FROM prices
            WHERE item_id = i.id
            AND timestamp < datetime('now', '-1 day')
        )
    """)
    row = cursor.fetchone()
    prev_value = row["prev_value"] if row and row["prev_value"] else total_value

    conn.close()

    return {
        **counts,
        "total_value": total_value,
        "total_cost": total_cost,
        "prev_value": prev_value,
        "daily_change": total_value - prev_value,
        "daily_change_pct": ((total_value - prev_value) / prev_value * 100) if prev_value else 0,
        "total_profit": total_value - total_cost if total_cost else None,
    }


def update_item_api_id(item_id: int, api_id: str) -> None:
    """Update the API ID for an item."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE items SET api_id = ?, updated_at = ? WHERE id = ?",
        (api_id, datetime.now().isoformat(), item_id)
    )
    conn.commit()
    conn.close()


def update_item_cost_basis(item_id: int, cost_basis: float) -> bool:
    """Update the cost basis (purchase price) for an item."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE items SET cost_basis = ?, updated_at = ? WHERE id = ?",
        (cost_basis, datetime.now().isoformat(), item_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
