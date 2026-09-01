"""Integrations package for external frameworks (LlamaIndex, Google SDK, Google ADK, etc.)."""

# Base Abstractions
from integrations.base import BaseHebrasAdapter, BaseIntegrationConfig

# LlamaIndex Integration
try:
    from integrations.llama_index.llama_index_integration import HebrasLLM
except ImportError:
    HebrasLLM = None  # type: ignore

# Google Antigravity SDK Integration
try:
    from integrations.google_sdk.google_sdk_integration import (
        HebrasAntigravityAgent,
        create_antigravity_agent,
        get_antigravity_config,
        stream_agent_response,
    )
except ImportError:
    HebrasAntigravityAgent = None  # type: ignore
    create_antigravity_agent = None  # type: ignore
    get_antigravity_config = None  # type: ignore
    stream_agent_response = None  # type: ignore

# Google ADK Integration
try:
    from integrations.google_adk.google_adk_integration import (
        HebrasADKAgent,
        HebrasADKConfig,
        create_adk_config,
    )
except ImportError:
    HebrasADKAgent = None  # type: ignore
    HebrasADKConfig = None  # type: ignore
    create_adk_config = None  # type: ignore

__all__ = [
    "BaseIntegrationConfig",
    "BaseHebrasAdapter",
    "HebrasLLM",
    "HebrasAntigravityAgent",
    "create_antigravity_agent",
    "get_antigravity_config",
    "stream_agent_response",
    "HebrasADKAgent",
    "HebrasADKConfig",
    "create_adk_config",
]
