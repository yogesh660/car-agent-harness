from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models import BaseChatModel

# hosted APIs rate-limit eval runs; their clients retry with backoff if asked to
_RETRYING_PROVIDERS = {"openai", "anthropic"}


def load_chat_model(model: str, base_url: str | None = None, max_retries: int = 6) -> BaseChatModel:
    """model is "<provider>:<name>", e.g. "ollama:qwen2.5:7b" or "openai:gpt-4o-mini".

    For a vLLM server, or any other OpenAI-compatible endpoint, use the openai provider plus
    base_url. The provider package has to be installed, e.g. uv sync --extra ollama.
    """
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {"temperature": 0}
    if base_url:
        kwargs["base_url"] = base_url
    provider = model.split(":", 1)[0]
    if provider in _RETRYING_PROVIDERS:
        kwargs["max_retries"] = max_retries
    if provider == "ollama":
        # Ollama's default context is small; system prompt + tool schemas + results overflow it
        # and get cut off silently
        kwargs["num_ctx"] = int(os.environ.get("CAR_AGENT_NUM_CTX", "8192"))
    return init_chat_model(model, **kwargs)
