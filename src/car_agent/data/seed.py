"""Generates a fake but realistic used-car market.

Using generated data for now so everything runs offline and tests are reproducible
(ADR 0003). Prices = new price * depreciation * mileage/power adjustments + ~6% noise.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from car_agent.db import SCHEMA
from car_agent.schemas import MARKET_YEAR, Body, Fuel, Transmission

DEFAULT_ROWS = 2500
DEFAULT_SEED = 42

CITIES = (
    "Munich",
    "Berlin",
    "Hamburg",
    "Cologne",
    "Frankfurt",
    "Stuttgart",
    "Dusseldorf",
    "Leipzig",
    "Nuremberg",
    "Hanover",
)

FUEL_PRICE_FACTOR: dict[Fuel, float] = {
    "petrol": 1.00,
    "diesel": 1.05,
    "hybrid": 1.08,
    "electric": 1.00,
}


@dataclass(frozen=True)
class ModelSpec:
    make: str
    model: str
    body: Body
    fuels: tuple[Fuel, ...]
    new_price_eur: int
    power_kw: tuple[int, int]
    first_year: int = 2012
    premium: bool = False


# fmt: off
CATALOG: tuple[ModelSpec, ...] = (
    #          make             model             body         fuels                             new €   kW range
    ModelSpec("Volkswagen",    "Golf",           "hatchback", ("petrol", "diesel", "hybrid"), 32_000, (81, 110)),
    ModelSpec("Volkswagen",    "Passat Variant", "estate",    ("petrol", "diesel"),           42_000, (110, 140)),
    ModelSpec("Volkswagen",    "ID.3",           "hatchback", ("electric",),                  40_000, (110, 150), 2020),
    ModelSpec("BMW",           "3 Series",       "saloon",    ("petrol", "diesel", "hybrid"), 48_000, (115, 190), premium=True),
    ModelSpec("BMW",           "X3",             "suv",       ("petrol", "diesel", "hybrid"), 58_000, (135, 210), premium=True),
    ModelSpec("Mercedes-Benz", "C-Class",        "saloon",    ("petrol", "diesel", "hybrid"), 50_000, (120, 190), premium=True),
    ModelSpec("Mercedes-Benz", "E-Class Estate", "estate",    ("petrol", "diesel"),           62_000, (145, 220), premium=True),
    ModelSpec("Audi",          "A4 Avant",       "estate",    ("petrol", "diesel"),           47_000, (110, 150), premium=True),
    ModelSpec("Audi",          "Q5",             "suv",       ("petrol", "diesel", "hybrid"), 57_000, (150, 210), premium=True),
    ModelSpec("Skoda",         "Octavia Combi",  "estate",    ("petrol", "diesel"),           33_000, (85, 110)),
    ModelSpec("Skoda",         "Fabia",          "hatchback", ("petrol",),                    20_000, (59, 85)),
    ModelSpec("Opel",          "Corsa",          "hatchback", ("petrol", "electric"),         21_000, (55, 100)),
    ModelSpec("Ford",          "Focus Turnier",  "estate",    ("petrol", "diesel"),           28_000, (85, 114)),
    ModelSpec("Toyota",        "Corolla",        "hatchback", ("hybrid",),                    31_000, (90, 103)),
    ModelSpec("Toyota",        "RAV4",           "suv",       ("hybrid",),                    42_000, (160, 163)),
    ModelSpec("Tesla",         "Model 3",        "saloon",    ("electric",),                  45_000, (200, 250), 2019, premium=True),
    ModelSpec("Hyundai",       "Tucson",         "suv",       ("petrol", "hybrid"),           36_000, (110, 169)),
    ModelSpec("Renault",       "Clio",           "hatchback", ("petrol", "hybrid"),           20_000, (67, 105)),
)
# fmt: on


def _price(
    spec: ModelSpec, year: int, mileage_km: int, power_kw: int, fuel: Fuel, rng: random.Random
) -> int:
    age = MARKET_YEAR - year
    low_kw, high_kw = spec.power_kw
    power_factor = 1 + 0.12 * (power_kw - low_kw) / max(high_kw - low_kw, 1)
    mileage_factor = max(0.55, 1 - mileage_km / 500_000)
    value = (
        spec.new_price_eur
        * FUEL_PRICE_FACTOR[fuel]
        * power_factor
        * (0.87**age)
        * mileage_factor
        * rng.gauss(1.0, 0.06)
    )
    return max(1_500, round(value / 50) * 50)


def _transmission(spec: ModelSpec, fuel: Fuel, rng: random.Random) -> Transmission:
    if fuel in ("electric", "hybrid"):
        return "automatic"
    return "automatic" if rng.random() < (0.85 if spec.premium else 0.40) else "manual"


def generate_rows(n: int = DEFAULT_ROWS, seed: int = DEFAULT_SEED) -> list[tuple[object, ...]]:
    # same n + seed -> same rows, tests depend on this
    rng = random.Random(seed)
    rows: list[tuple[object, ...]] = []
    for listing_id in range(1, n + 1):
        spec = rng.choice(CATALOG)
        fuel = rng.choice(spec.fuels)
        year = rng.randint(spec.first_year, MARKET_YEAR - 1)
        age = MARKET_YEAR - year
        mileage_km = max(1_000, int(max(age, 0.5) * rng.uniform(8_000, 22_000)))
        power_kw = rng.randint(*spec.power_kw)
        rows.append(
            (
                listing_id,
                spec.make,
                spec.model,
                year,
                mileage_km,
                fuel,
                spec.body,
                _transmission(spec, fuel, rng),
                power_kw,
                _price(spec, year, mileage_km, power_kw, fuel, rng),
                rng.choice(CITIES),
            )
        )
    return rows


def seed_database(db_path: Path, n: int = DEFAULT_ROWS, seed: int = DEFAULT_SEED) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    rows = generate_rows(n, seed)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO listings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.close()
    return len(rows)
