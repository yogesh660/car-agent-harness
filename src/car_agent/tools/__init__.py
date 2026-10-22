"""Tool registry.

Tools are plain functions (conn, validated input) -> pydantic output. No LangChain in
here on purpose, see ADR 0002. agent/tools.py wraps them for the graph.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from car_agent.tools.compare import CompareListingsInput, compare_listings
from car_agent.tools.pricing import EstimatePriceInput, estimate_price
from car_agent.tools.search import SearchListingsInput, search_listings


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str  # the model reads this, write it for the model
    input_model: type[BaseModel]
    fn: Callable[[sqlite3.Connection, Any], BaseModel]


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="search_listings",
        description=(
            "Search cars for sale by make, model, fuel, body style, gearbox, city, price, "
            "mileage and year. Returns the total number of matches and the first few listings."
        ),
        input_model=SearchListingsInput,
        fn=search_listings,
    ),
    ToolSpec(
        name="estimate_price",
        description=(
            "Estimate the market price of a car from comparable listings, either for an "
            "existing listing_id or for make/model/year/mileage. Gives a verdict "
            "(below_market, fair, above_market) when there is an asking price."
        ),
        input_model=EstimatePriceInput,
        fn=estimate_price,
    ),
    ToolSpec(
        name="compare_listings",
        description=(
            "Compare 2 to 4 listings side by side: age, km per year, price per kW and market "
            "estimate. Also names the cheapest, lowest-mileage and best-value listing."
        ),
        input_model=CompareListingsInput,
        fn=compare_listings,
    ),
)

TOOLS_BY_NAME = {spec.name: spec for spec in TOOLS}


def run_tool(name: str, conn: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    """Validate args, run the tool, return JSON-able data.

    Bad input or "not found" comes back as {"error": ...} instead of raising, so the
    model gets to see what went wrong and can try again.
    """
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {"error": f"Unknown tool {name!r}"}
    try:
        params = spec.input_model.model_validate(args)
        return spec.fn(conn, params).model_dump(mode="json")
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors()
        )
        return {"error": f"Invalid arguments: {problems}"}
    except ValueError as exc:
        return {"error": str(exc)}
