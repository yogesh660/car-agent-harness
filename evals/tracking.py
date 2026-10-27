"""Optional MLflow logging for eval runs (uv sync --extra tracking).

One MLflow run per eval run: model and fingerprints as params, the summary as metrics,
per-case results as a JSON artifact. Comparing runs in the MLflow UI then answers
"did this prompt change help?" without digging through files.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from car_agent.agent.prompts import SYSTEM_PROMPT
from car_agent.tools import TOOLS

EXPERIMENT = "car-agent-evals"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def fingerprints(cases_text: str) -> dict[str, str]:
    """Short hashes of everything that changes agent behaviour, to tell runs apart."""
    tools = [
        {"name": t.name, "description": t.description, "schema": t.input_model.model_json_schema()}
        for t in TOOLS
    ]
    return {
        "prompt_sha": _sha(SYSTEM_PROMPT),
        "tools_sha": _sha(json.dumps(tools, sort_keys=True)),
        "cases_sha": _sha(cases_text),
    }


def log_run(
    params: dict[str, Any],
    metrics: dict[str, float],
    cases: list[dict[str, Any]],
    tags: dict[str, str] | None = None,
) -> str:
    import mlflow

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run() as run:
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.log_dict({"cases": cases}, "results.json")
        if tags:
            mlflow.set_tags(tags)
        return str(run.info.run_id)
