"""Google ADK integration for hebras-ai."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from google.adk.agents.llm_agent import Agent
from google.adk.labs.openai import OpenAILlm
from openai import AsyncOpenAI

from integrations.google_adk.callbacks import (
    adk_after_agent_callback,
    adk_after_model_callback,
    adk_after_tool_callback,
    adk_before_agent_callback,
    adk_before_model_callback,
    adk_before_tool_callback,
    adk_on_model_error_callback,
    adk_on_tool_error_callback,
)
from integrations.google_adk.logging import get_adk_logger, setup_adk_logging

logger = get_adk_logger("integration")


@dataclass
class GoogleADKConfig:
    """Configuration for Google ADK integration."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "Gemini 3.7 Flash"
    name: str = "root_agent"
    description: str | None = None
    instruction: str | None = None
    tools: list[Callable[..., Any]] = field(default_factory=list)
    enable_logging: bool = True
    log_dir: str | Path | None = None
    log_level: str = "DEBUG"
    enable_console_logging: bool = False

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
    enable_logging: bool = True,
    log_dir: str | Path | None = None,
    log_level: str = "DEBUG",
    enable_console_logging: bool = False,
    **kwargs: Any,
) -> Agent:
    """Create and return an official Google ADK Agent configured for hebras-ai.

    Args:
        config: Optional pre-configured GoogleADKConfig.
        base_url: hebras-ai API base URL (default: http://localhost:8000/v1).
        model: Model identifier exposed by hebras-ai (e.g. 'Gemini 3.8 Flash').
        name: Name of the agent.
        description: Optional description of the agent.
        instruction: System instruction for the agent.
        tools: Optional list of tool callables.
        enable_logging: If True, configures organized rotating debug logs in log/adk/.
        log_dir: Custom directory for ADK logs (default: <workspace>/log/adk).
        log_level: Logging severity level (default: 'DEBUG').
        enable_console_logging: If True, outputs logs to stdout in addition to log files.
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
        cfg_enable_logging = config.enable_logging
        cfg_log_dir = config.log_dir
        cfg_log_level = config.log_level
        cfg_enable_console = config.enable_console_logging
    else:
        cfg_base_url = base_url
        cfg_model = model
        cfg_name = name
        cfg_description = description
        cfg_instruction = instruction
        cfg_tools = tools or []
        cfg_enable_logging = enable_logging
        cfg_log_dir = log_dir
        cfg_log_level = log_level
        cfg_enable_console = enable_console_logging

    if cfg_enable_logging:
        setup_adk_logging(
            log_dir=cfg_log_dir,
            level=cfg_log_level,
            enable_console=cfg_enable_console,
        )

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

    if cfg_enable_logging:
        agent_kwargs["before_agent_callback"] = kwargs.pop(
            "before_agent_callback", adk_before_agent_callback
        )
        agent_kwargs["after_agent_callback"] = kwargs.pop(
            "after_agent_callback", adk_after_agent_callback
        )
        agent_kwargs["before_model_callback"] = kwargs.pop(
            "before_model_callback", adk_before_model_callback
        )
        agent_kwargs["after_model_callback"] = kwargs.pop(
            "after_model_callback", adk_after_model_callback
        )
        agent_kwargs["on_model_error_callback"] = kwargs.pop(
            "on_model_error_callback", adk_on_model_error_callback
        )
        agent_kwargs["before_tool_callback"] = kwargs.pop(
            "before_tool_callback", adk_before_tool_callback
        )
        agent_kwargs["after_tool_callback"] = kwargs.pop(
            "after_tool_callback", adk_after_tool_callback
        )
        agent_kwargs["on_tool_error_callback"] = kwargs.pop(
            "on_tool_error_callback", adk_on_tool_error_callback
        )

    agent_kwargs.update(kwargs)
    filtered_kwargs = {k: v for k, v in agent_kwargs.items() if v is not None}
    return Agent(**filtered_kwargs)