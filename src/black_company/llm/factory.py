"""Chat model factory — DeepSeek via OpenAI-compatible HTTP API."""

from __future__ import annotations

import os
from typing import Any

# https://api-docs.deepseek.com/
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


def create_deepseek_chat(
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.2,
) -> Any:
    """
    Build a LangChain chat model pointed at DeepSeek.

    Requires extra deps: ``pip install 'black-company[llm]'``.

    Env (optional overrides):
    - DEEPSEEK_API_KEY — required unless `api_key` is passed
    - DEEPSEEK_MODEL — default ``deepseek-chat``
    - DEEPSEEK_BASE_URL — default ``https://api.deepseek.com``
    """
    try:
        from langchain_openai import ChatOpenAI as _ChatOpenAI
    except ImportError as e:
        msg = "Install LLM support: pip install 'black-company[llm]'"
        raise ImportError(msg) from e

    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        msg = "Set DEEPSEEK_API_KEY or pass api_key= to create_deepseek_chat()."
        raise ValueError(msg)

    return _ChatOpenAI(
        model=model or os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        api_key=key,
        base_url=base_url or os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
        temperature=temperature,
    )
