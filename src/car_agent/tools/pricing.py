"""estimate_price: market value from comparable listings."""

from __future__ import annotations

import sqlite3
import statistics
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from car_agent.schemas import Listing, normalize_make

MIN_COMPARABLES = 5

MatchLevel = Literal["close", "wider", "widest"]
Verdict = Literal["below_market", "fair", "above_market"]

# try tight matches first, loosen until we have enough cars: (level, year gap, km gap)
_MATCH_LEVELS: tuple[tuple[MatchLevel, int, int | None], ...] = (
    ("close", 1, 25_000),
    ("wider", 2, 50_000),
    ("widest", 3, None),
)


class EstimatePriceInput(BaseModel):
    listing_id: int | None = Field(
        default=None,
        description="Value an existing listing. If set, the car fields below are ignored.",
    )
    make: str | None = Field(default=None, description="Manufacturer, e.g. 'Skoda'.")
    model: str | None = Field(default=None, description="Exact model name, e.g. 'Octavia Combi'.")
    year: int | None = Field(default=None, ge=1990, le=2030, description="Registration year.")
    mileage_km: int | None = Field(default=None, ge=0, description="Odometer reading in km.")
    asking_price_eur: int | None = Field(
        default=None,
        ge=0,
        description="Price to judge against the market. Defaults to the listing price.",
    )

    @model_validator(mode="after")
    def _has_a_car(self) -> EstimatePriceInput:
        if self.listing_id is None and None in (self.make, self.model, self.year, self.mileage_km):
            raise ValueError("Provide listing_id, or all of make, model, year and mileage_km")
        return self


class PriceEstimate(BaseModel):
    make: str
    model: str
    year: int
    mileage_km: int
    estimate_eur: int = Field(description="Median price of comparable listings.")
    low_eur: int = Field(description="25th percentile of comparable prices.")
    high_eur: int = Field(description="75th percentile of comparable prices.")
    comparables: int = Field(description="Number of listings the estimate is based on.")
    match_level: MatchLevel = Field(description="How loosely comparables had to be matched.")
    asking_price_eur: int | None = None
    verdict: Verdict | None = Field(
        default=None,
        description="Asking price below, within or above the 25th-75th percentile band.",
    )


def _comparable_prices(
    conn: sqlite3.Connection,
    make: str,
    model: str,
    year: int,
    mileage_km: int,
    exclude_id: int | None,
) -> tuple[list[int], MatchLevel] | None:
    for level, year_gap, km_gap in _MATCH_LEVELS:
        sql = (
            "SELECT price_eur FROM listings WHERE make = ? COLLATE NOCASE "
            "AND model = ? COLLATE NOCASE AND ABS(year - ?) <= ? AND id != ?"
        )
        args: list[object] = [make, model, year, year_gap, exclude_id or -1]
        if km_gap is not None:
            sql += " AND ABS(mileage_km - ?) <= ?"
            args += [mileage_km, km_gap]
        prices = [row[0] for row in conn.execute(sql, args)]
        if len(prices) >= MIN_COMPARABLES:
            return prices, level
    return None


def estimate_price(conn: sqlite3.Connection, params: EstimatePriceInput) -> PriceEstimate:
    asking: int | None
    if params.listing_id is not None:
        row = conn.execute("SELECT * FROM listings WHERE id = ?", [params.listing_id]).fetchone()
        if row is None:
            raise ValueError(f"Listing {params.listing_id} not found")
        listing = Listing.from_row(row)
        make, model, year, mileage = listing.make, listing.model, listing.year, listing.mileage_km
        asking = (
            params.asking_price_eur if params.asking_price_eur is not None else listing.price_eur
        )
    else:
        p = params
        # the validator already checks this; repeated so mypy knows they are set
        if p.make is None or p.model is None or p.year is None or p.mileage_km is None:
            raise ValueError("Provide listing_id, or all of make, model, year and mileage_km")
        make, model, year, mileage = normalize_make(p.make), p.model.strip(), p.year, p.mileage_km
        asking = p.asking_price_eur

    found = _comparable_prices(conn, make, model, year, mileage, params.listing_id)
    if found is None:
        raise ValueError(
            f"Fewer than {MIN_COMPARABLES} comparable listings for {make} {model} around {year}. "
            "Check the model name with search_listings."
        )
    prices, level = found
    q1, median, q3 = statistics.quantiles(prices, n=4, method="inclusive")

    verdict: Verdict | None = None
    if asking is not None:
        verdict = "below_market" if asking < q1 else "above_market" if asking > q3 else "fair"

    return PriceEstimate(
        make=make,
        model=model,
        year=year,
        mileage_km=mileage,
        estimate_eur=round(median),
        low_eur=round(q1),
        high_eur=round(q3),
        comparables=len(prices),
        match_level=level,
        asking_price_eur=asking,
        verdict=verdict,
    )
