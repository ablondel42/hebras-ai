"""Integrations package for external frameworks (LlamaIndex, google-antigravity, etc.)."""
try:
    from integrations.hebras_llm import HebrasLLM
except ImportError:
    HebrasLLM = None  # type: ignore

__all__ = ["HebrasLLM"]
