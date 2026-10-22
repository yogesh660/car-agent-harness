"""Settings come from env vars only. No config files to hunt for."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path("data/listings.db")
DEFAULT_MODEL = "ollama:qwen2.5:7b"
DEFAULT_MAX_STEPS = 8


@dataclass(frozen=True)
class Settings:
    # CAR_AGENT_DB         sqlite file
    # CAR_AGENT_MODEL      "<provider>:<model>", e.g. "openai:gpt-4o-mini"
    # CAR_AGENT_BASE_URL   optional, e.g. a vLLM server
    # CAR_AGENT_MAX_STEPS  max model calls per question

    db_path: Path
    model: str
    base_url: str | None
    max_steps: int

    @classmethod
    def from_env(cls) -> Settings:
        max_steps = int(os.environ.get("CAR_AGENT_MAX_STEPS", DEFAULT_MAX_STEPS))
        if max_steps < 1:
            raise ValueError("CAR_AGENT_MAX_STEPS must be at least 1")
        return cls(
            db_path=Path(os.environ.get("CAR_AGENT_DB", str(DEFAULT_DB_PATH))),
            model=os.environ.get("CAR_AGENT_MODEL", DEFAULT_MODEL),
            base_url=os.environ.get("CAR_AGENT_BASE_URL") or None,
            max_steps=max_steps,
        )
