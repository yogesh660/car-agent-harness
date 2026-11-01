"""SQLite access. Tools get a read-only connection, so they cannot change the data."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

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


class DataRow(Protocol):
    """The keyed row shape returned by supported database drivers."""

    def keys(self) -> list[str]: ...

    def __getitem__(self, key: str | int) -> Any: ...


class QueryResult(Protocol):
    """Subset of a DB-API cursor used by marketplace tools."""

    def fetchone(self) -> DataRow | None: ...

    def fetchall(self) -> list[DataRow]: ...

    def __iter__(self) -> Iterator[DataRow]: ...


class ReadConnection(Protocol):
    """Read-only database operations available to tools."""

    def execute(self, query: str, parameters: Sequence[object] = ()) -> QueryResult: ...

    def close(self) -> None: ...


def connect_readonly(db_path: Path) -> ReadConnection:
    """Open the listings database in read-only mode."""
    if not db_path.exists():
        raise FileNotFoundError(f"No database at {db_path}. Run `make seed` to create it.")
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # sqlite's stubs expose broader row/parameter unions than the small interface tools use.
    return cast(ReadConnection, conn)
