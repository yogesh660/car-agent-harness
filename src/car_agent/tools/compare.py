"""compare_listings: side-by-side view of 2-4 listings with derived metrics."""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel, Field, field_validator

from car_agent.schemas import MARKET_YEAR, Listing
from car_agent.tools.pricing import EstimatePriceInput, PriceEstimate, estimate_price


class CompareListingsInput(BaseModel):
    listing_ids: list[int] = Field(
        min_length=2, max_length=4, description="IDs of 2 to 4 listings to compare."
    )

    @field_validator("listing_ids")
    @classmethod
    def _unique(cls, ids: list[int]) -> list[int]:
        if len(set(ids)) != len(ids):
            raise ValueError("listing_ids must not contain duplicates")
        return ids


class ComparedListing(BaseModel):
    listing: Listing
    age_years: int
    km_per_year: int
    eur_per_kw: float
    market: PriceEstimate | None = Field(
        description="Market estimate, or null when there are too few comparables."
    )


class CompareListingsOutput(BaseModel):
    listings: list[ComparedListing]
    cheapest_id: int
    lowest_mileage_id: int
    best_value_id: int | None = Field(
        description="Listing priced furthest below its market estimate, if any estimate exists."
    )


def compare_listings(
    conn: sqlite3.Connection, params: CompareListingsInput
) -> CompareListingsOutput:
    placeholders = ", ".join("?" for _ in params.listing_ids)
    rows = conn.execute(
        f"SELECT * FROM listings WHERE id IN ({placeholders})", params.listing_ids
    ).fetchall()
    by_id = {row["id"]: Listing.from_row(row) for row in rows}
    missing = [i for i in params.listing_ids if i not in by_id]
    if missing:
        raise ValueError(f"Listing(s) not found: {missing}")

    compared: list[ComparedListing] = []
    for listing_id in params.listing_ids:
        listing = by_id[listing_id]
        age = max(MARKET_YEAR - listing.year, 1)
        try:
            market: PriceEstimate | None = estimate_price(
                conn, EstimatePriceInput(listing_id=listing_id)
            )
        except ValueError:
            market = None
        compared.append(
            ComparedListing(
                listing=listing,
                age_years=MARKET_YEAR - listing.year,
                km_per_year=round(listing.mileage_km / age),
                eur_per_kw=round(listing.price_eur / listing.power_kw, 1),
                market=market,
            )
        )

    priced = [c for c in compared if c.market is not None]
    best_value = (
        min(priced, key=lambda c: c.listing.price_eur / c.market.estimate_eur)  # type: ignore[union-attr]
        if priced
        else None
    )
    return CompareListingsOutput(
        listings=compared,
        cheapest_id=min(compared, key=lambda c: c.listing.price_eur).listing.id,
        lowest_mileage_id=min(compared, key=lambda c: c.listing.mileage_km).listing.id,
        best_value_id=best_value.listing.id if best_value else None,
    )
