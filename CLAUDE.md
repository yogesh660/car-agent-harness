# CLAUDE.md

Notes for coding agents (and people) working in this repo. Read this before changing anything.

## What this is

A LangGraph agent that answers questions about a used-car marketplace: search listings,
estimate prices, compare cars. Data is synthetic and generated locally.

## Commands

Always use the make targets, they are exactly what CI runs. Dependencies are managed with uv.

- `make setup` - install everything with uv (once)
- `make lock` - update `uv.lock` after editing dependencies in `pyproject.toml`
- `make seed` - rebuild `data/listings.db`
- `make test` - pytest
- `make lint` / `make format` - ruff
- `make typecheck` - mypy strict on `src/`
- `make check` - lint + typecheck + test. **Must pass before you commit.**
- `make eval` - runs the agent against `evals/cases.jsonl`. Needs a model (see README), so it
  is not part of `make check`. Run it when you touch prompts, tool descriptions or schemas.
- `make eval-smoke` - the small smoke subset, same as the PR check
- `make eval-baseline` - re-record `evals/baseline.json` (only when a drop is understood and accepted)
- `make tools` - prints every tool and its input schema, handy before editing one
- `make mlflow` - MLflow UI for eval runs logged with `EVAL_ARGS=--mlflow`

## Layout

```
src/car_agent/
  schemas.py        Listing model, enums, make and city aliases
  db.py             sqlite schema + read-only connection
  data/seed.py      deterministic data generator
  tools/            one file per tool, plain python + pydantic, NO langchain imports
  tools/__init__.py the registry (TOOLS) and run_tool()
  agent/            langgraph graph, langchain tool wrappers, prompt, model loading
  cli.py            car-agent seed | tools | ask
evals/
  cases.jsonl       ground truth: question -> expected tool calls, categories, smoke flag
  scoring.py        did the agent call the right tools with the right args?
  grounding.py      are the numbers in the answer backed by tool results?
  judge.py          optional LLM-as-judge for all other claims
  run.py            runner, metrics, baseline gate, GitHub summary
  baseline.json     accepted scores the gate compares against (per suite)
tests/unit/         one test file per tool: tests/unit/test_<tool_name>.py
tests/agent/        graph and eval-runner tests with a scripted fake model (no network)
tests/agent/scripted.py  the fake model; use it for anything that needs a model
tests/test_harness.py  checks on the repo itself (docs, tests, schemas, eval set)
docs/adr/           why things are the way they are
site/               public case-study page, deployed by .github/workflows/pages.yml
```

## Adding or changing a tool

1. Write it in `src/car_agent/tools/<name>.py`: an `XInput` model, an output model and a
   function `(conn, XInput) -> Output`.
2. Every input field needs `Field(description=...)`. The model only sees the JSON schema.
3. Register it in `TOOLS` in `src/car_agent/tools/__init__.py`.
4. Add `tests/unit/test_<name>.py`. `tests/test_harness.py` fails until you do.
5. Add at least three cases to `evals/cases.jsonl` that should trigger it, one marked
   `"smoke": true`. `tests/test_harness.py` checks this.
6. Raise `ValueError` with a clear message for "not found" or "not enough data".
   `run_tool` turns it into an error the model can read and recover from.

## Rules

- Tools are read-only. Never open a writable connection outside `data/seed.py`.
- No SQL built from user input. Values go in as `?` params; column names and ORDER BY come
  from constants in the tool file.
- Keep `tools/` free of langchain/langgraph imports (ADR 0002). Framework code lives in `agent/`.
- Tests must not call a real model or the network. Use `tests/agent/scripted.py`.
- Don't change `data/seed.py` output casually. Seeded numbers are asserted in tests and eval
  cases reference listing ids (checked by `tests/test_harness.py`). If you must, regenerate
  the affected cases and say so in the PR.
- Eval cases are ground truth. Fix the agent, not the case, unless the case is wrong; then
  explain why in the PR.
- Don't lower `evals/baseline.json` to get a PR through.
- Don't edit `.github/workflows/` or loosen mypy/ruff settings to make a check pass. Fix the code.
- New dependency? Add it to `pyproject.toml`, run `make lock`, commit `uv.lock`, and explain
  why in the PR.

## Branches, merges and releases

Nothing is committed to `main` directly. Every change goes through a short-lived branch and
lands only when its checks are green.

1. Branch from an up-to-date `main`: `feature/<topic>` for new work (one milestone or part
   of one), `fix/<topic>` for bugs. Keep it small enough to review in one sitting.
2. Commit in small logical steps; `make check` passes before every commit.
3. Push the branch. CI runs on it (plus any eval workflow the change triggers). Fix until
   every required workflow is green on the branch head.
4. Merge with a merge commit so the branch stays visible in history:
   `git checkout main && git pull && git merge --no-ff <branch> -m "Merge <branch>: <one-line summary>"`,
   then push `main`. The housekeeping workflow deletes merged `feature/` and `fix/` branches.
5. CI runs again on `main`. If it fails, fix it on a `fix/` branch straight away.
6. When a roadmap milestone is complete, end its heading in `docs/ROADMAP.md` with "(done)".
   After the merge, the housekeeping workflow tags `main` as `v0.<n+1>.0` (M0 -> v0.1.0,
   M1 -> v0.2.0, ...). Don't create or push tags by hand.

## Done means

- `make check` passes locally and CI is green on the branch
- merged into `main` through the flow above, never pushed to it directly
- new behaviour has a test, new tool has an eval case
- if you changed how to work in this repo, this file is updated too
- PR description filled in using `.github/pull_request_template.md`
