"""Build the case-study page assets: architecture images and chart data.

    make site

Writes site/img/architecture-wide.svg, site/img/architecture-tall.svg and site/data.js.
Chart data comes from the repo itself (eval cases, seeded market) and from recorded CI eval
runs listed in EVAL_RUNS, so every number on the page can be traced.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from car_agent.data.seed import generate_rows
from car_agent.schemas import MARKET_YEAR
from svgdiagram import Box, Diagram

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REPO = "https://github.com/yogesh660/car-agent-harness"

# Smoke-suite runs in GitHub Actions (qwen2.5:7b on CPU, temperature 0). Update when a new
# baseline is accepted; ids link to the runs.
EVAL_RUNS = {
    "baseline": {
        "label": "Current agent",
        "run": 40451093767,
        "metrics": {"pass": 0.6923, "tools": 1.0, "args": 0.8462, "grounded": 1.0},
        "failed": [
            "multi-search-then-price",
            "price-asking",
            "search-auto-suv",
            "search-cheapest-ev",
        ],
    },
    "prompt_rules": {
        "label": "With extra prompt rules (reverted)",
        "run": 40449444103,
        "metrics": {"pass": 0.6923, "tools": 0.9231, "args": 0.7692, "grounded": 1.0},
    },
}


def eval_data() -> dict[str, object]:
    cases = [
        json.loads(line) for line in (ROOT / "evals/cases.jsonl").read_text().splitlines() if line
    ]
    failed = set(EVAL_RUNS["baseline"]["failed"])  # type: ignore[arg-type]
    smoke_total: Counter[str] = Counter()
    smoke_pass: Counter[str] = Counter()
    full: Counter[str] = Counter()
    smoke_count: Counter[str] = Counter()
    for c in cases:
        full[c["category"]] += 1
        if c.get("smoke"):
            smoke_count[c["category"]] += 1
            smoke_total[c["category"]] += 1
            smoke_pass[c["category"]] += c["id"] not in failed
    order = [cat for cat, _ in full.most_common()]
    return {
        "runs": {k: {**v, "url": f"{REPO}/actions/runs/{v['run']}"} for k, v in EVAL_RUNS.items()},
        "by_category": [
            {"category": cat, "passed": smoke_pass[cat], "total": smoke_total[cat]}
            for cat in order
            if smoke_total[cat]
        ],
        "composition": [
            {"category": cat, "smoke": smoke_count[cat], "full_only": full[cat] - smoke_count[cat]}
            for cat in order
        ],
        "cases": len(cases),
    }


def market_data() -> dict[str, object]:
    prices: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in generate_rows():
        fuel, year, price = str(row[5]), int(row[3]), int(row[9])  # type: ignore[call-overload]
        prices[fuel][MARKET_YEAR - year].append(price)
    return {
        fuel: [
            {"age": age, "median": round(statistics.median(v)), "n": len(v)}
            for age, v in sorted(by_age.items())
            if len(v) >= 5
        ]
        for fuel, by_age in sorted(prices.items())
    }


def architecture_wide() -> str:
    d = Diagram(1240, 700, "car-agent-harness architecture")
    d.group(24, 24, 220, 350, "Clients")
    chat = d.box(
        Box(
            44,
            70,
            180,
            104,
            "Chat UI",
            "streams answers,\nshows tool calls",
            "M3",
            "io",
            planned=True,
        )
    )
    cli = d.box(Box(44, 220, 180, 104, "CLI / API", "car-agent ask\nFastAPI in M3", "today", "io"))

    d.group(270, 24, 360, 350, "Agent · LangGraph")
    agent = d.box(
        Box(
            292,
            70,
            316,
            104,
            "Agent node",
            "LLM + JSON schemas of the tools;\npicks tools, writes the answer",
            "model",
            "model",
        )
    )
    node = d.box(
        Box(
            292,
            220,
            316,
            104,
            "ToolNode",
            "validates arguments, returns errors\nto the model; step budget of 8",
            "runtime",
            "code",
        )
    )

    d.group(656, 24, 270, 350, "Tools · Python + pydantic")
    tools = [
        d.box(Box(676, 62, 230, 88, "search_listings", "filters, sort, limit", "tool", "code")),
        d.box(Box(676, 160, 230, 88, "estimate_price", "median of comparables", "tool", "code")),
        d.box(Box(676, 258, 230, 88, "compare_listings", "2-4 cars side by side", "tool", "code")),
    ]

    d.group(952, 24, 264, 350, "Data")
    sqlite = d.box(
        Box(972, 62, 224, 88, "Listings · SQLite", "read-only, ? params only", "today", "data")
    )
    d.box(
        Box(
            972,
            160,
            224,
            88,
            "Postgres + pgvector",
            "RAG over specs, reviews",
            "M2",
            "data",
            planned=True,
        )
    )
    d.box(
        Box(972, 258, 224, 88, "Neo4j graph", "models, engines, issues", "M2", "data", planned=True)
    )

    models = d.box(
        Box(
            292,
            404,
            316,
            84,
            "Model providers",
            "Ollama · vLLM · OpenAI-compatible",
            "swap by env var",
            "model",
        )
    )

    d.group(24, 520, 1192, 156, "Quality and delivery")
    evals = d.box(
        Box(
            44,
            562,
            270,
            94,
            "Eval suite",
            "56 questions · tool scoring\nnumber grounding · LLM judge",
            "evals",
            "ops",
        )
    )
    mlflow = d.box(
        Box(
            340,
            562,
            250,
            94,
            "MLflow",
            "every eval run, prompt and\ntool hashes, per-case results",
            "tracking",
            "ops",
        )
    )
    ci = d.box(
        Box(
            616,
            562,
            300,
            94,
            "GitHub Actions",
            "CI on every branch · eval gate\non agent changes · nightly suite",
            "ci/cd",
            "ops",
        )
    )
    d.box(
        Box(
            942,
            562,
            254,
            94,
            "Housekeeping + Pages",
            "tags milestones, cleans branches,\npublishes this page",
            "ci/cd",
            "ops",
        )
    )

    d.arrow(cli.edge("r"), (agent.x, cli.cy), bend="hv")
    d.arrow(chat.edge("r"), agent.edge("l"), dashed=True)
    d.arrow(agent.edge("b"), node.edge("t"), "tool calls")
    for t in tools:
        d.arrow(node.edge("r"), t.edge("l"), bend="hvh")
    for t in tools:
        d.arrow(t.edge("r"), sqlite.edge("l"), bend="hvh")
    d.arrow((agent.x + 40, node.y + node.h), (agent.x + 40, models.y), "LLM calls")
    d.arrow(evals.edge("r"), mlflow.edge("l"))
    d.arrow(ci.edge("l"), mlflow.edge("r"))
    d.arrow((evals.cx, evals.y), (evals.cx, cli.y + cli.h), "replays questions", dashed=True)
    d.legend(270, 506)
    return d.svg()


def architecture_tall() -> str:
    d = Diagram(460, 1560, "car-agent-harness architecture")
    d.group(20, 20, 420, 150, "Clients")
    cli = d.box(Box(38, 60, 186, 92, "CLI / API", "car-agent ask", "today", "io"))
    d.box(Box(236, 60, 186, 92, "Chat UI", "tool-call trace", "M3", "io", planned=True))

    d.group(20, 196, 420, 268, "Agent · LangGraph")
    agent = d.box(
        Box(
            38,
            236,
            384,
            98,
            "Agent node",
            "LLM + tool schemas; picks tools,\nwrites the answer",
            "model",
            "model",
        )
    )
    node = d.box(
        Box(
            38,
            350,
            384,
            98,
            "ToolNode",
            "validates arguments, errors back\nto the model; step budget 8",
            "runtime",
            "code",
        )
    )
    models = d.box(
        Box(
            196,
            490,
            226,
            98,
            "Model providers",
            "Ollama · vLLM\nOpenAI-compatible",
            "swap by env var",
            "model",
        )
    )

    d.group(20, 600, 420, 330, "Tools · Python + pydantic")
    t1 = d.box(Box(38, 640, 384, 80, "search_listings", "filters, sort, limit", "tool", "code"))
    d.box(Box(38, 734, 384, 80, "estimate_price", "median of comparables", "tool", "code"))
    t3 = d.box(Box(38, 828, 384, 80, "compare_listings", "2-4 cars side by side", "tool", "code"))

    d.group(20, 956, 420, 300, "Data")
    sqlite = d.box(
        Box(38, 996, 384, 76, "Listings · SQLite", "read-only, ? params only", "today", "data")
    )
    d.box(
        Box(
            38,
            1084,
            384,
            76,
            "Postgres + pgvector",
            "RAG over specs and reviews",
            "M2",
            "data",
            planned=True,
        )
    )
    d.box(
        Box(
            38,
            1172,
            384,
            76,
            "Neo4j graph",
            "models, engines, known issues",
            "M2",
            "data",
            planned=True,
        )
    )

    d.group(20, 1282, 420, 258, "Quality and delivery")
    d.box(Box(38, 1322, 186, 98, "Eval suite", "56 questions\ngrounding · judge", "evals", "ops"))
    d.box(Box(236, 1322, 186, 98, "MLflow", "runs, hashes,\nper-case results", "tracking", "ops"))
    d.box(Box(38, 1432, 186, 92, "GitHub Actions", "CI · eval gate\nnightly suite", "ci/cd", "ops"))
    d.box(Box(236, 1432, 186, 92, "Housekeeping", "tags, branches,\nthis page", "ci/cd", "ops"))

    d.arrow(cli.edge("b"), (cli.cx, agent.y))
    d.arrow(agent.edge("b"), node.edge("t"))
    d.arrow((models.cx, node.y + node.h), (models.cx, models.y))
    d.arrow((node.x + 60, node.y + node.h), (node.x + 60, t1.y))
    d.arrow(t3.edge("b"), sqlite.edge("t"))
    return d.svg()


def main() -> None:
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    (SITE / "img" / "architecture-wide.svg").write_text(architecture_wide())
    (SITE / "img" / "architecture-tall.svg").write_text(architecture_tall())
    data = {"evals": eval_data(), "market": market_data()}
    (SITE / "data.js").write_text(
        "// generated by scripts/site_assets.py - do not edit by hand\n"
        f"window.SITE_DATA = {json.dumps(data, separators=(',', ':'))};\n"
    )
    print("wrote site/img/*.svg and site/data.js")


if __name__ == "__main__":
    main()
