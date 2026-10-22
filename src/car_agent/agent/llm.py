from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel


def load_chat_model(model: str, base_url: str | None = None) -> BaseChatModel:
    """model is "<provider>:<name>", e.g. "ollama:qwen2.5:7b" or "openai:gpt-4o-mini".

    For a vLLM server use the openai provider plus base_url (vLLM speaks the OpenAI API).
    The provider package has to be installed, e.g. pip install -e ".[ollama]".
    """
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {"temperature": 0}
    if base_url:
        kwargs["base_url"] = base_url
    return init_chat_model(model, **kwargs)
