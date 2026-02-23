"""
LLM factory — creates OpenAI LLM instances from centralized settings.
"""
from llama_index.llms.openai import OpenAI
from app.config.settings import (
    LLM_MODEL, LLM_SECURITY_MODEL, LLM_SUMMARY_MODEL,
    LLM_TIMEOUT, LLM_SECURITY_TIMEOUT, LLM_SUMMARY_TIMEOUT,
)


def get_llm(**overrides) -> OpenAI:
    """General-purpose LLM (chat, slide generation, tool calling)."""
    defaults = {"model": LLM_MODEL, "request_timeout": LLM_TIMEOUT}
    defaults.update(overrides)
    return OpenAI(**defaults)


def get_security_llm() -> OpenAI:
    """Deterministic LLM for security classification (temperature=0)."""
    return OpenAI(model=LLM_SECURITY_MODEL, temperature=0, request_timeout=LLM_SECURITY_TIMEOUT)


def get_summary_llm() -> OpenAI:
    """LLM for conversation summary generation."""
    return OpenAI(model=LLM_SUMMARY_MODEL, request_timeout=LLM_SUMMARY_TIMEOUT)
