import sqlite3
from pathlib import Path

import pytest

from car_agent.data.seed import CATALOG, generate_rows, seed_database
from car_agent.db import connect_readonly
from car_agent.schemas import BODIES, FUELS, MARKET_YEAR, TRANSMISSIONS


def test_same_seed_gives_same_rows():
    assert generate_rows(300, seed=7) == generate_rows(300, seed=7)
    assert generate_rows(300, seed=7) != generate_rows(300, seed=8)


def test_seed_database_writes_all_rows(tmp_path: Path):
    path = tmp_path / "x.db"
    assert seed_database(path, n=150) == 150
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 150


def test_reseeding_replaces_old_data(tmp_path: Path):
    path = tmp_path / "x.db"
    seed_database(path, n=100)
    seed_database(path, n=40)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 40


def test_values_are_in_range(conn: sqlite3.Connection):
    first_year = {(s.make, s.model): s.first_year for s in CATALOG}
    for row in conn.execute("SELECT * FROM listings"):
        assert row["fuel"] in FUELS
        assert row["body"] in BODIES
        assert row["transmission"] in TRANSMISSIONS
        assert first_year[(row["make"], row["model"])] <= row["year"] < MARKET_YEAR
        assert row["price_eur"] >= 1500
        assert row["mileage_km"] >= 1000
        if row["fuel"] in ("electric", "hybrid"):
            assert row["transmission"] == "automatic"


def test_older_cars_are_cheaper_on_average(conn: sqlite3.Connection):
    # sanity check on the depreciation model, the price estimator relies on it
    new = conn.execute(
        "SELECT AVG(price_eur) FROM listings WHERE model = 'Golf' AND year >= 2021"
    ).fetchone()[0]
    old = conn.execute(
        "SELECT AVG(price_eur) FROM listings WHERE model = 'Golf' AND year <= 2015"
    ).fetchone()[0]
    assert new > old * 1.5


def test_readonly_connection_cannot_write(db_path: Path):
    c = connect_readonly(db_path)
    with pytest.raises(sqlite3.OperationalError):
        c.execute("DELETE FROM listings")
    c.close()


def test_missing_db_has_helpful_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="make seed"):
        connect_readonly(tmp_path / "nope.db")
