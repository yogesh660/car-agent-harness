# One entry point for humans, CI and coding agents. Keep targets in sync with CLAUDE.md
# (tests/test_harness.py fails if CLAUDE.md mentions a target that does not exist).

RUN := uv run
Q ?= Find me a diesel estate under 15000 euros with low mileage
EVAL_ARGS ?=

.DEFAULT_GOAL := help
.PHONY: help setup lock seed lint format typecheck test check eval eval-smoke eval-baseline ask tools mlflow clean

help: ## List available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install everything (all model providers, MLflow, dev tools) and the pre-commit hook
	uv sync --all-extras
	$(RUN) pre-commit install

lock: ## Re-resolve dependencies into uv.lock after editing pyproject.toml
	uv lock

seed: ## Build data/listings.db from the deterministic generator
	$(RUN) car-agent seed

lint: ## Ruff lint and format check (no changes)
	$(RUN) ruff check src tests evals
	$(RUN) ruff format --check src tests evals

format: ## Auto-fix lint issues and format code
	$(RUN) ruff check --fix src tests evals
	$(RUN) ruff format src tests evals

typecheck: ## Mypy (strict) on src/
	$(RUN) mypy

test: ## Run the full pytest suite
	$(RUN) pytest

check: lint typecheck test ## Everything CI runs. Must pass before any commit.

eval: ## Full eval set against the configured model (EVAL_ARGS="--judge --mlflow" for more)
	$(RUN) python -m evals.run $(EVAL_ARGS)

eval-smoke: ## The small smoke set that also runs on PRs
	$(RUN) python -m evals.run --smoke $(EVAL_ARGS)

eval-baseline: ## Run full + smoke evals and save their scores to evals/baseline.json
	$(RUN) python -m evals.run --write-baseline $(EVAL_ARGS)
	$(RUN) python -m evals.run --smoke --write-baseline $(EVAL_ARGS)

ask: ## Ask the agent one question: make ask Q="..."
	$(RUN) car-agent ask --trace "$(Q)"

tools: ## Print every agent tool with its input schema
	$(RUN) car-agent tools

mlflow: ## MLflow UI on http://localhost:5000 for runs logged with --mlflow
	$(RUN) mlflow ui --backend-store-uri sqlite:///mlflow.db

clean: ## Remove generated data and caches
	rm -rf data/*.db evals/results .pytest_cache .mypy_cache .ruff_cache
