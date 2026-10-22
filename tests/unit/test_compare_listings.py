import sqlite3

import pytest
from pydantic import ValidationError

from car_agent.schemas import MARKET_YEAR
from car_agent.tools.compare import CompareListingsInput, compare_listings


def ids_for(conn, model, n):
    rows = conn.execute("SELECT id FROM listings WHERE model = ? LIMIT ?", [model, n])
    return [r[0] for r in rows]


def test_compare_two_listings(conn: sqlite3.Connection):
    ids = ids_for(conn, "Golf", 2)
    out = compare_listings(conn, CompareListingsInput(listing_ids=ids))

    assert [c.listing.id for c in out.listings] == ids  # keeps the requested order
    for c in out.listings:
        assert c.age_years == MARKET_YEAR - c.listing.year
        assert c.eur_per_kw == pytest.approx(c.listing.price_eur / c.listing.power_kw, abs=0.1)
        assert c.market is not None

    cheapest = min(out.listings, key=lambda c: c.listing.price_eur)
    assert out.cheapest_id == cheapest.listing.id
    assert out.best_value_id in ids


def test_mixed_models(conn: sqlite3.Connection):
    ids = ids_for(conn, "Golf", 1) + ids_for(conn, "X3", 1) + ids_for(conn, "Model 3", 1)
    out = compare_listings(conn, CompareListingsInput(listing_ids=ids))
    assert len(out.listings) == 3
    lowest = min(out.listings, key=lambda c: c.listing.mileage_km)
    assert out.lowest_mileage_id == lowest.listing.id


def test_missing_ids_are_reported(conn: sqlite3.Connection):
    real = ids_for(conn, "Golf", 1)
    with pytest.raises(ValueError, match="999999"):
        compare_listings(conn, CompareListingsInput(listing_ids=[*real, 999_999]))


@pytest.mark.parametrize("ids", [[1], [1, 2, 3, 4, 5], [3, 3]])
def test_invalid_id_lists(ids):
    with pytest.raises(ValidationError):
        CompareListingsInput(listing_ids=ids)
