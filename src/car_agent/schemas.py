"""Domain types used by the tools and the agent."""

from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict

Fuel = Literal["petrol", "diesel", "hybrid", "electric"]
Body = Literal["hatchback", "saloon", "estate", "suv"]
Transmission = Literal["manual", "automatic"]

FUELS: tuple[Fuel, ...] = ("petrol", "diesel", "hybrid", "electric")
BODIES: tuple[Body, ...] = ("hatchback", "saloon", "estate", "suv")
TRANSMISSIONS: tuple[Transmission, ...] = ("manual", "automatic")

# the synthetic market is generated "as of" this year (used for car age)
MARKET_YEAR = 2025


# what people (and models) type vs what the listings say
MAKE_ALIASES = {
    "vw": "Volkswagen",
    "mercedes": "Mercedes-Benz",
    "merc": "Mercedes-Benz",
    "benz": "Mercedes-Benz",
    "skoda": "Skoda",
    "škoda": "Skoda",
}


def normalize_make(make: str) -> str:
    cleaned = make.strip()
    return MAKE_ALIASES.get(cleaned.lower(), cleaned)


class Listing(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    make: str
    model: str
    year: int
    mileage_km: int
    fuel: Fuel
    body: Body
    transmission: Transmission
    power_kw: int
    price_eur: int
    city: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Listing:
        return cls.model_validate(dict(row))
