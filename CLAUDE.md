# CLAUDE.md

Notes for coding agents (and people) working in this repo. Read this before changing anything.

## What this is

A LangGraph agent that answers questions about a used-car marketplace: search listings,
estimate prices, compare cars. Data is synthetic and generated locally.

## Commands

Always use the make targets, they are exactly what CI runs.

- `make setup` - install with dev tools (once)
- `make seed` - rebuild `data/listings.db`
- `make test` - pytest
- `make lint` / `make format` - ruff
- `make typecheck` - mypy strict on `src/`
- `make check` - lint + typecheck + test. **Must pass before you commit.**
- `make eval` - runs the agent against `evals/cases.jsonl`. Needs a model (see README), so it
  is not part of `make check`. Run it when you touch prompts, tool descriptions or schemas.
- `make tools` - prints every tool and its input schema, handy before editing one

## Layout

```
src/car_agent/
  schemas.py        Listing model, enums, make aliases
  db.py             sqlite schema + read-only connection
  data/seed.py      deterministic data generator
  tools/            one file per tool, plain python + pydantic, NO langchain imports
  tools/__init__.py the registry (TOOLS) and run_tool()
  agent/            langgraph graph, langchain tool wrappers, prompt, model loading
  cli.py            car-agent seed | tools | ask
evals/              eval cases + scoring + runner
tests/unit/         one test file per tool: tests/unit/test_<tool_name>.py
tests/agent/        graph tests with a scripted fake model (no network)
tests/test_harness.py  checks on the repo itself (docs, tests, schemas)
docs/adr/           why things are the way they are
```

## Adding or changing a tool

1. Write it in `src/car_agent/tools/<name>.py`: an `XInput` model, an output model and a
   function `(conn, XInput) -> Output`.
2. Every input field needs `Field(description=...)`. The model only sees the JSON schema.
3. Register it in `TOOLS` in `src/car_agent/tools/__init__.py`.
4. Add `tests/unit/test_<name>.py`. `tests/test_harness.py` fails until you do.
5. Add at least one case to `evals/cases.jsonl` that should trigger it.
6. Raise `ValueError` with a clear message for "not found" or "not enough data".
   `run_tool` turns it into an error the model can read and recover from.

## Rules

- Tools are read-only. Never open a writable connection outside `data/seed.py`.
- No SQL built from user input. Values go in as `?` params; column names and ORDER BY come
  from constants in the tool file.
- Keep `tools/` free of langchain/langgraph imports (ADR 0002). Framework code lives in `agent/`.
- Tests must not call a real model or the network. Use the `ScriptedModel` in
  `tests/agent/test_graph.py`.
- Don't change `data/seed.py` output casually. Seeded numbers are asserted in tests and eval
  cases reference listing ids. If you must, say so in the PR.
- Don't edit `.github/workflows/` or loosen mypy/ruff settings to make a check pass. Fix the code.
- New dependency? Add it to `pyproject.toml` and explain why in the PR.

## Done means

- `make check` passes locally
- new behaviour has a test, new tool has an eval case
- if you changed how to work in this repo, this file is updated too
- PR description filled in using `.github/pull_request_template.md`
