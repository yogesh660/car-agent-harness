import sqlite3

import pytest
from pydantic import ValidationError

from car_agent.tools.pricing import MIN_COMPARABLES, EstimatePriceInput, estimate_price


def estimate(conn, **kwargs):
    return estimate_price(conn, EstimatePriceInput(**kwargs))


def test_estimate_for_described_car(conn: sqlite3.Connection):
    est = estimate(conn, make="Volkswagen", model="Golf", year=2019, mileage_km=60_000)
    assert est.low_eur <= est.estimate_eur <= est.high_eur
    assert est.comparables >= MIN_COMPARABLES
    assert est.verdict is None  # no asking price given


def test_verdicts(conn: sqlite3.Connection):
    car = {"make": "Volkswagen", "model": "Golf", "year": 2019, "mileage_km": 60_000}
    base = estimate(conn, **car)
    assert estimate(conn, **car, asking_price_eur=base.low_eur - 2000).verdict == "below_market"
    assert estimate(conn, **car, asking_price_eur=base.estimate_eur).verdict == "fair"
    assert estimate(conn, **car, asking_price_eur=base.high_eur + 2000).verdict == "above_market"


def test_estimate_for_listing_uses_its_price_and_skips_itself(conn: sqlite3.Connection):
    row = conn.execute("SELECT * FROM listings WHERE model = 'Golf' LIMIT 1").fetchone()
    est = estimate(conn, listing_id=row["id"])
    assert est.asking_price_eur == row["price_eur"]
    assert est.verdict is not None

    # comparables must not include the listing itself
    with_self = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE model = 'Golf' AND ABS(year - ?) <= 1 "
        "AND ABS(mileage_km - ?) <= 25000",
        [row["year"], row["mileage_km"]],
    ).fetchone()[0]
    if est.match_level == "close":
        assert est.comparables == with_self - 1


def test_newer_car_is_worth_more(conn: sqlite3.Connection):
    old = estimate(conn, make="BMW", model="3 Series", year=2015, mileage_km=120_000)
    new = estimate(conn, make="BMW", model="3 Series", year=2022, mileage_km=30_000)
    assert new.estimate_eur > old.estimate_eur


def test_unknown_model_raises(conn: sqlite3.Connection):
    with pytest.raises(ValueError, match="comparable"):
        estimate(conn, make="Volkswagen", model="Beetle", year=2018, mileage_km=50_000)


def test_unknown_listing_raises(conn: sqlite3.Connection):
    with pytest.raises(ValueError, match="not found"):
        estimate(conn, listing_id=999_999)


def test_needs_listing_or_full_description():
    with pytest.raises(ValidationError):
        EstimatePriceInput(make="BMW", model="X3")
