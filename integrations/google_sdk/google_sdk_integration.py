"""Google Antigravity SDK integration for hebras-ai.

Provides the `HebrasAntigravityAgent` class and helper functions to seamlessly connect
the official `google-antigravity` Python SDK to a local or remote `hebras-ai` backend.
"""
import asyncio
import logging
import sys
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from google.antigravity import Agent, LocalOpenAIAgentConfig
from google.antigravity.hooks import policy

from integrations.base import BaseIntegrationConfig

logger = logging.getLogger(__name__)


def get_antigravity_config(
    base_url: str = "http://localhost:8000/v1",
    model: str = "Gemini 3.7 Flash",
    system_instructions: str | None = None,
    tools: Sequence[Callable[..., Any]] | None = None,
    policies: Sequence[Any] | None = None,
    **kwargs: Any,
) -> LocalOpenAIAgentConfig:
    """Build a LocalOpenAIAgentConfig pre-configured for the hebras-ai server.

    Args:
        base_url: The hebras-ai OpenAI-compatible API base URL (default: http://localhost:8000/v1).
        model: Model identifier exposed by hebras-ai (e.g. 'Gemini 3.7 Flash').
        system_instructions: Optional system instructions / persona prompt for the agent.
        tools: Optional list of Python callables to register as tools.
        policies: Optional list of safety/execution policies (defaults to [policy.allow_all()]).
        **kwargs: Additional keyword arguments passed to LocalOpenAIAgentConfig.

    Returns:
        Configured LocalOpenAIAgentConfig instance.
    """
    effective_policies = list(policies) if policies is not None else [policy.allow_all()]

    config_kwargs: dict[str, Any] = {
        "base_url": base_url,
        "model": model,
        "policies": effective_policies,
    }
    if system_instructions is not None:
        config_kwargs["system_instructions"] = system_instructions
    if tools is not None:
        config_kwargs["tools"] = list(tools)

    config_kwargs.update(kwargs)
    return LocalOpenAIAgentConfig(**config_kwargs)


class HebrasAntigravityAgent:
    """High-level async context manager wrapping google.antigravity.Agent for hebras-ai.

    Standardizes agent configuration, lifecycle management, tool execution,
    and streaming token consumption against a local or remote hebras-ai instance.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Gemini 3.7 Flash",
        agent: str = "default",
        reflection: str = "high",
        system_instructions: str | None = None,
        tools: Sequence[Callable[..., Any]] | None = None,
        policies: Sequence[Any] | None = None,
        config: BaseIntegrationConfig | LocalOpenAIAgentConfig | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(config, LocalOpenAIAgentConfig):
            self.agent_config = config
            self.base_config = BaseIntegrationConfig(
                api_base=getattr(config, "base_url", base_url),
                model=getattr(config, "model", model),
                agent=agent,
                reflection=reflection,
            )
        elif isinstance(config, BaseIntegrationConfig):
            self.base_config = config
            self.agent_config = get_antigravity_config(
                base_url=config.api_base,
                model=config.model,
                system_instructions=system_instructions,
                tools=tools,
                policies=policies,
                **kwargs,
            )
        else:
            self.base_config = BaseIntegrationConfig(
                api_base=base_url,
                model=model,
                agent=agent,
                reflection=reflection,
            )
            self.agent_config = get_antigravity_config(
                base_url=base_url,
                model=model,
                system_instructions=system_instructions,
                tools=tools,
                policies=policies,
                **kwargs,
            )

        self._agent: Agent = Agent(self.agent_config)

    @property
    def agent(self) -> Agent:
        """The underlying google.antigravity.Agent instance."""
        return self._agent

    @property
    def config(self) -> LocalOpenAIAgentConfig:
        """The active LocalOpenAIAgentConfig instance."""
        return self.agent_config

    @property
    def conversation_id(self) -> str | None:
        """The active conversation ID if the agent has started."""
        if hasattr(self._agent, "conversation_id"):
            return self._agent.conversation_id
        return self.base_config.conversation_id

    async def __aenter__(self) -> "HebrasAntigravityAgent":
        await self._agent.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._agent.__aexit__(exc_type, exc_val, exc_tb)

    async def chat(self, prompt: str) -> Any:
        """Send a prompt to the agent and return the raw response object.

        Args:
            prompt: User message string.

        Returns:
            The response object from google.antigravity.Agent.
        """
        return await self._agent.chat(prompt)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt and stream string tokens incrementally.

        Args:
            prompt: User message string.

        Yields:
            Response tokens as strings.
        """
        response = await self.chat(prompt)
        async for token in response:
            yield token


def create_antigravity_agent(
    base_url: str = "http://localhost:8000/v1",
    model: str = "Gemini 3.7 Flash",
    system_instructions: str | None = None,
    tools: Sequence[Callable[..., Any]] | None = None,
    policies: Sequence[Any] | None = None,
    config: LocalOpenAIAgentConfig | BaseIntegrationConfig | None = None,
    **kwargs: Any,
) -> Agent:
    """Instantiate a google.antigravity.Agent configured for hebras-ai.

    Args:
        base_url: The hebras-ai API base URL.
        model: Model identifier exposed by hebras-ai.
        system_instructions: Optional system persona prompt.
        tools: Optional list of Python tool callables.
        policies: Optional execution policies.
        config: Optional pre-built config.
        **kwargs: Additional keyword arguments forwarded to config builder.

    Returns:
        An instantiated google.antigravity.Agent instance.
    """
    if isinstance(config, LocalOpenAIAgentConfig):
        return Agent(config)

    agent_wrapper = HebrasAntigravityAgent(
        base_url=base_url,
        model=model,
        system_instructions=system_instructions,
        tools=tools,
        policies=policies,
        config=config,
        **kwargs,
    )
    return agent_wrapper.agent


async def stream_agent_response(
    agent: Agent | HebrasAntigravityAgent,
    prompt: str,
) -> AsyncIterator[str]:
    """Send a chat prompt to the agent and yield tokens as an async iterator.

    Args:
        agent: An active google.antigravity.Agent or HebrasAntigravityAgent.
        prompt: Prompt string to send.

    Yields:
        String tokens streamed from the model response.
    """
    if isinstance(agent, HebrasAntigravityAgent):
        async for token in agent.stream(prompt):
            yield token
    else:
        response = await agent.chat(prompt)
        async for token in response:
            yield token


if __name__ == "__main__":
    async def main():
        print("Running HebrasAntigravityAgent demonstration...")
        async with HebrasAntigravityAgent(
            base_url="http://localhost:8000/v1",
            model="Gemini 3.7 Flash",
            system_instructions="You are a helpful assistant powered by hebras-ai.",
        ) as agent:
            prompt = "Explain in one sentence what makes Antigravity modular."
            print(f"User: {prompt}\nAgent: ", end="")
            async for token in agent.stream(prompt):
                sys.stdout.write(token)
                sys.stdout.flush()
            print()

    asyncio.run(main())
