"""Google Antigravity SDK integration for hebras-ai."""
from dataclasses import dataclass, field
from typing import Any, Callable

from google.antigravity import Agent, LocalOpenAIAgentConfig
from google.antigravity.hooks import policy


@dataclass
class GoogleSDKConfig:
    """Configuration for Google Antigravity SDK integration."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "Gemini 3.7 Flash"
    system_instructions: str | None = None
    tools: list[Callable[..., Any]] = field(default_factory=list)
    policies: list[Any] = field(default_factory=lambda: [policy.allow_all()])


def create_agent(config: GoogleSDKConfig | None = None, **kwargs: Any) -> Agent:
    """Create a Google Antigravity Agent instance configured for hebras-ai."""
    cfg = config or GoogleSDKConfig(**kwargs)
    agent_config = LocalOpenAIAgentConfig(
        base_url=cfg.base_url,
        model=cfg.model,
        system_instructions=cfg.system_instructions,
        tools=cfg.tools if cfg.tools else None,
        policies=cfg.policies,
    )
    return Agent(agent_config)

