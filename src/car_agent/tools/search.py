"""search_listings: filter and sort cars for sale."""

from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from car_agent.schemas import Body, Fuel, Listing, Transmission, normalize_make

SortBy = Literal["price_asc", "price_desc", "mileage_asc", "year_desc"]

# only these strings ever go into ORDER BY; everything else is a bound param
_ORDER_BY: dict[SortBy, str] = {
    "price_asc": "price_eur ASC",
    "price_desc": "price_eur DESC",
    "mileage_asc": "mileage_km ASC",
    "year_desc": "year DESC",
}


class SearchListingsInput(BaseModel):
    make: str | None = Field(
        default=None, description="Manufacturer, e.g. 'BMW'. Case-insensitive."
    )
    model: str | None = Field(
        default=None,
        description="Model name or part of it, e.g. 'Golf' or 'Octavia'. Case-insensitive.",
    )
    fuel: Fuel | None = Field(default=None, description="Fuel type.")
    body: Body | None = Field(
        default=None, description="Body style. Use 'estate' for station wagons."
    )
    transmission: Transmission | None = Field(default=None, description="Gearbox type.")
    city: str | None = Field(
        default=None, description="City where the car is listed, e.g. 'Munich'."
    )
    min_price_eur: int | None = Field(default=None, ge=0, description="Lowest price in euros.")
    max_price_eur: int | None = Field(default=None, ge=0, description="Highest price in euros.")
    max_mileage_km: int | None = Field(
        default=None, ge=0, description="Highest odometer reading in km."
    )
    min_year: int | None = Field(
        default=None, ge=1990, le=2030, description="Earliest registration year."
    )
    sort_by: SortBy = Field(default="price_asc", description="Result order.")
    limit: int = Field(default=5, ge=1, le=20, description="Number of listings to return (1-20).")

    @model_validator(mode="after")
    def _price_range_is_ordered(self) -> SearchListingsInput:
        if (
            self.min_price_eur is not None
            and self.max_price_eur is not None
            and self.min_price_eur > self.max_price_eur
        ):
            raise ValueError("min_price_eur must not be greater than max_price_eur")
        return self


class SearchListingsOutput(BaseModel):
    total_matches: int = Field(description="All listings matching the filters.")
    listings: list[Listing] = Field(description="The first `limit` matches in the chosen order.")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_listings(conn: sqlite3.Connection, params: SearchListingsInput) -> SearchListingsOutput:
    clauses: list[str] = []
    args: list[object] = []

    if params.make:
        clauses.append("make = ? COLLATE NOCASE")
        args.append(normalize_make(params.make))
    if params.model:
        clauses.append("model LIKE ? ESCAPE '\\' COLLATE NOCASE")
        args.append(f"%{_escape_like(params.model.strip())}%")
    if params.city:
        clauses.append("city = ? COLLATE NOCASE")
        args.append(params.city.strip())
    for column, value in (
        ("fuel", params.fuel),
        ("body", params.body),
        ("transmission", params.transmission),
    ):
        if value:
            clauses.append(f"{column} = ?")
            args.append(value)
    for column, op, num in (
        ("price_eur", ">=", params.min_price_eur),
        ("price_eur", "<=", params.max_price_eur),
        ("mileage_km", "<=", params.max_mileage_km),
        ("year", ">=", params.min_year),
    ):
        if num is not None:
            clauses.append(f"{column} {op} ?")
            args.append(num)

    where = " AND ".join(clauses) or "1 = 1"
    total = conn.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM listings WHERE {where} ORDER BY {_ORDER_BY[params.sort_by]}, id LIMIT ?",
        [*args, params.limit],
    ).fetchall()
    return SearchListingsOutput(
        total_matches=total, listings=[Listing.from_row(row) for row in rows]
    )
