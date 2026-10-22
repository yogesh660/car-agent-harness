"""SQLite access. Tools get a read-only connection, so they cannot change the data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE listings (
    id            INTEGER PRIMARY KEY,
    make          TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    year          INTEGER NOT NULL,
    mileage_km    INTEGER NOT NULL,
    fuel          TEXT    NOT NULL,
    body          TEXT    NOT NULL,
    transmission  TEXT    NOT NULL,
    power_kw      INTEGER NOT NULL,
    price_eur     INTEGER NOT NULL,
    city          TEXT    NOT NULL
);
CREATE INDEX idx_listings_make_model ON listings (make, model);
CREATE INDEX idx_listings_price ON listings (price_eur);
"""


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the listings database in read-only mode."""
    if not db_path.exists():
        raise FileNotFoundError(f"No database at {db_path}. Run `make seed` to create it.")
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
