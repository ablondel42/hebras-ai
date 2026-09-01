"""Google ADK integration for hebras-ai."""
from dataclasses import dataclass, field
from typing import Any, Callable

from google.adk.agents.llm_agent import Agent
from google.adk.labs.openai import OpenAILlm
from openai import AsyncOpenAI


@dataclass
class GoogleADKConfig:
    """Configuration for Google ADK integration."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "Gemini 3.7 Flash"
    name: str = "root_agent"
    description: str | None = None
    instruction: str | None = None
    tools: list[Callable[..., Any]] = field(default_factory=list)

    def create_agent(self, **kwargs: Any) -> Agent:
        """Return an official Google ADK Agent configured to use hebras-ai."""
        return create_agent(config=self, **kwargs)


def create_agent(
    config: GoogleADKConfig | None = None,
    base_url: str = "http://localhost:8000/v1",
    model: str = "Gemini 3.7 Flash",
    name: str = "root_agent",
    description: str | None = None,
    instruction: str | None = None,
    tools: list[Callable[..., Any]] | None = None,
    **kwargs: Any,
) -> Agent:
    """Create and return an official Google ADK Agent configured for hebras-ai.

    Args:
        config: Optional pre-configured GoogleADKConfig.
        base_url: hebras-ai API base URL (default: http://localhost:8000/v1).
        model: Model identifier exposed by hebras-ai (e.g. 'Gemini 3.7 Flash').
        name: Name of the agent.
        description: Optional description of the agent.
        instruction: System instruction for the agent.
        tools: Optional list of tool callables.
        **kwargs: Additional parameters forwarded to Agent.

    Returns:
        Configured google.adk.agents.llm_agent.Agent instance.
    """
    if config is not None:
        cfg_base_url = config.base_url
        cfg_model = config.model
        cfg_name = config.name
        cfg_description = config.description
        cfg_instruction = config.instruction
        cfg_tools = config.tools
    else:
        cfg_base_url = base_url
        cfg_model = model
        cfg_name = name
        cfg_description = description
        cfg_instruction = instruction
        cfg_tools = tools or []

    openai_client = AsyncOpenAI(
        base_url=cfg_base_url,
        api_key="hebras",
    )
    llm = OpenAILlm(
        model=cfg_model,
        client=openai_client,
    )

    agent_kwargs: dict[str, Any] = {
        "name": cfg_name,
        "model": llm,
        "description": cfg_description,
        "instruction": cfg_instruction,
        "tools": cfg_tools,
    }
    agent_kwargs.update(kwargs)
    filtered_kwargs = {k: v for k, v in agent_kwargs.items() if v is not None}
    return Agent(**filtered_kwargs)