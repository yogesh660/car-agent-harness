# One entry point for humans, CI and coding agents. Keep targets in sync with CLAUDE.md
# (tests/test_harness.py fails if CLAUDE.md mentions a target that does not exist).

PYTHON ?= python
Q ?= Find me a diesel estate under 15000 euros with low mileage

.DEFAULT_GOAL := help
.PHONY: help setup seed lint format typecheck test check eval ask tools clean

help: ## List available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install the package with dev tools and enable pre-commit hooks
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install

seed: ## Build data/listings.db from the deterministic generator
	$(PYTHON) -m car_agent.cli seed

lint: ## Ruff lint and format check (no changes)
	ruff check src tests evals
	ruff format --check src tests evals

format: ## Auto-fix lint issues and format code
	ruff check --fix src tests evals
	ruff format src tests evals

typecheck: ## Mypy (strict) on src/
	mypy

test: ## Run the full pytest suite
	$(PYTHON) -m pytest

check: lint typecheck test ## Everything CI runs. Must pass before any commit.

eval: ## Score the agent on evals/cases.jsonl (needs a configured model, see README)
	$(PYTHON) -m evals.run

ask: ## Ask the agent one question: make ask Q="..."
	$(PYTHON) -m car_agent.cli ask --trace "$(Q)"

tools: ## Print every agent tool with its input schema
	$(PYTHON) -m car_agent.cli tools

clean: ## Remove generated data and caches
	rm -rf data/*.db evals/results .pytest_cache .mypy_cache .ruff_cache
