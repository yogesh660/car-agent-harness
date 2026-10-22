"""car-agent command line.

car-agent seed                 build data/listings.db
car-agent tools                print tool names + input schemas
car-agent ask "question"       ask the agent (needs a model, see README)
"""

from __future__ import annotations

import argparse
import json
import sys

from car_agent.config import Settings
from car_agent.data.seed import DEFAULT_ROWS, DEFAULT_SEED, seed_database
from car_agent.tools import TOOLS


def cmd_seed(args: argparse.Namespace, settings: Settings) -> int:
    n = seed_database(settings.db_path, n=args.rows, seed=args.seed)
    print(f"Wrote {n} listings to {settings.db_path}")
    return 0


def cmd_tools(_: argparse.Namespace, __: Settings) -> int:
    for spec in TOOLS:
        print(f"## {spec.name}\n{spec.description}\n")
        print(json.dumps(spec.input_model.model_json_schema(), indent=2))
        print()
    return 0


def cmd_ask(args: argparse.Namespace, settings: Settings) -> int:
    # imported here so `seed` and `tools` work without the LLM stack installed
    from car_agent.agent.graph import build_graph, run_agent
    from car_agent.agent.llm import load_chat_model
    from car_agent.agent.tools import build_tools

    if not settings.db_path.exists():
        print(f"No database yet, seeding {settings.db_path} ...", file=sys.stderr)
        seed_database(settings.db_path)

    graph = build_graph(
        load_chat_model(settings.model, settings.base_url), build_tools(settings.db_path)
    )
    result = run_agent(graph, args.question, max_steps=settings.max_steps)

    if args.trace:
        for call in result.tool_calls:
            print(f"[tool] {call.name} {json.dumps(call.args)}", file=sys.stderr)
    print(result.answer)
    return 1 if result.stopped_early else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="car-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="build the listings database")
    p_seed.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    p_seed.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_seed.set_defaults(func=cmd_seed)

    p_tools = sub.add_parser("tools", help="print the agent's tools")
    p_tools.set_defaults(func=cmd_tools)

    p_ask = sub.add_parser("ask", help="ask the agent a question")
    p_ask.add_argument("question")
    p_ask.add_argument("--trace", action="store_true", help="print tool calls to stderr")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args(argv)
    return int(args.func(args, Settings.from_env()))


if __name__ == "__main__":
    sys.exit(main())
