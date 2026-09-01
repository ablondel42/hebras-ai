"""Integrations package for external frameworks (Google SDK, Google ADK, LlamaIndex)."""

# Google Antigravity SDK
try:
    from integrations.google_sdk.google_sdk_integration import GoogleSDKConfig, create_agent
except ImportError:
    GoogleSDKConfig = None  # type: ignore
    create_agent = None  # type: ignore

# Google ADK
try:
    from integrations.google_adk.google_adk_integration import GoogleADKConfig
except ImportError:
    GoogleADKConfig = None  # type: ignore

# LlamaIndex
try:
    from integrations.llama_index.llama_index_integration import HebrasLLM, LlamaIndexConfig
except ImportError:
    HebrasLLM = None  # type: ignore
    LlamaIndexConfig = None  # type: ignore

__all__ = [
    "GoogleSDKConfig",
    "create_agent",
    "GoogleADKConfig",
    "HebrasLLM",
    "LlamaIndexConfig",
]


