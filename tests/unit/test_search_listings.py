import sqlite3

import pytest
from pydantic import ValidationError

from car_agent.tools.search import SearchListingsInput, search_listings


def search(conn, **kwargs):
    return search_listings(conn, SearchListingsInput(**kwargs))


def test_no_filters_returns_default_limit(conn: sqlite3.Connection):
    out = search(conn)
    assert out.total_matches == 2500
    assert len(out.listings) == 5


def test_filters_are_all_applied(conn: sqlite3.Connection):
    out = search(
        conn,
        fuel="diesel",
        body="estate",
        max_price_eur=15_000,
        max_mileage_km=150_000,
        min_year=2016,
        limit=20,
    )
    assert out.listings, "expected some diesel estates in the seeded data"
    for car in out.listings:
        assert car.fuel == "diesel"
        assert car.body == "estate"
        assert car.price_eur <= 15_000
        assert car.mileage_km <= 150_000
        assert car.year >= 2016
    assert out.total_matches >= len(out.listings)


def test_make_and_city_ignore_case(conn: sqlite3.Connection):
    a = search(conn, make="bmw", city="MUNICH", limit=20)
    b = search(conn, make="BMW", city="Munich", limit=20)
    assert a == b
    assert a.total_matches > 0


@pytest.mark.parametrize(("alias", "make"), [("VW", "Volkswagen"), ("mercedes", "Mercedes-Benz")])
def test_common_make_aliases(conn: sqlite3.Connection, alias, make):
    out = search(conn, make=alias)
    assert out.total_matches > 0
    assert all(car.make == make for car in out.listings)


@pytest.mark.parametrize("city", ["München", "muenchen", " Munich "])
def test_german_city_names(conn: sqlite3.Connection, city):
    assert search(conn, city=city) == search(conn, city="Munich")


def test_model_matches_partial_name(conn: sqlite3.Connection):
    out = search(conn, model="octavia")
    assert out.total_matches > 0
    assert all(car.model == "Octavia Combi" for car in out.listings)


def test_like_wildcards_are_escaped(conn: sqlite3.Connection):
    assert search(conn, model="%").total_matches == 0
    assert search(conn, model="_").total_matches == 0


@pytest.mark.parametrize(
    ("sort_by", "key", "reverse"),
    [
        ("price_asc", "price_eur", False),
        ("price_desc", "price_eur", True),
        ("mileage_asc", "mileage_km", False),
        ("year_desc", "year", True),
    ],
)
def test_sort_order(conn: sqlite3.Connection, sort_by, key, reverse):
    out = search(conn, make="Volkswagen", sort_by=sort_by, limit=20)
    values = [getattr(car, key) for car in out.listings]
    assert values == sorted(values, reverse=reverse)


def test_nothing_found_is_not_an_error(conn: sqlite3.Connection):
    out = search(conn, make="Lada")
    assert out.total_matches == 0
    assert out.listings == []


def test_bad_inputs_rejected():
    with pytest.raises(ValidationError):
        SearchListingsInput(min_price_eur=20_000, max_price_eur=10_000)
    with pytest.raises(ValidationError):
        SearchListingsInput(fuel="steam")
    with pytest.raises(ValidationError):
        SearchListingsInput(limit=500)
