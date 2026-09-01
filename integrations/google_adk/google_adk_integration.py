"""Google Agent Development Kit (ADK) integration for hebras-ai.

Provides the `HebrasADKAgent` class and configuration builders to bridge Google
Agent Development Kit (ADK) workflows to the hebras-ai OpenAI-compatible backend.
"""
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import Field

from integrations.base import BaseHebrasAdapter, BaseIntegrationConfig

logger = logging.getLogger(__name__)


class HebrasADKConfig(BaseIntegrationConfig):
    """Configuration container for Google Agent Development Kit (ADK) integration."""

    system_instruction: str | None = Field(
        default=None,
        description="System instructions / persona for the agent",
    )
    tools: list[Any] = Field(
        default_factory=list,
        description="List of registered tools / functions",
    )
    temperature: float | None = Field(
        default=None,
        description="Sampling temperature",
    )


class HebrasADKAgent(BaseHebrasAdapter):
    """Agent adapter for Google Agent Development Kit (ADK) workflows."""

    def __init__(
        self,
        config: HebrasADKConfig | None = None,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Gemini 3.7 Flash",
        agent: str = "default",
        system_instruction: str | None = None,
        tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if config is None:
            config = HebrasADKConfig(
                api_base=base_url,
                model=model,
                agent=agent,
                system_instruction=system_instruction,
                tools=tools or [],
                **kwargs,
            )
        super().__init__(config=config)
        self.adk_config: HebrasADKConfig = config

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Synchronously execute a chat completion."""
        payload = self.adk_config.build_payload(prompt)
        with httpx.Client(timeout=self.adk_config.timeout) as client:
            resp = client.post(f"{self.adk_config.api_base}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "system_fingerprint" in data:
            self.conversation_id = data["system_fingerprint"]

        return data["choices"][0]["message"]["content"] or ""

    async def acomplete(self, prompt: str, **kwargs: Any) -> str:
        """Asynchronously execute a chat completion."""
        payload = self.adk_config.build_payload(prompt)
        async with httpx.AsyncClient(timeout=self.adk_config.timeout) as client:
            resp = await client.post(f"{self.adk_config.api_base}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "system_fingerprint" in data:
            self.conversation_id = data["system_fingerprint"]

        return data["choices"][0]["message"]["content"] or ""

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronously stream response tokens."""
        payload = self.adk_config.build_payload(prompt, stream=True)
        async with httpx.AsyncClient(timeout=self.adk_config.timeout) as client:
            async with client.stream("POST", f"{self.adk_config.api_base}/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    chunk_data = json.loads(data_str)
                    if chunk_data.get("system_fingerprint"):
                        self.conversation_id = chunk_data["system_fingerprint"]

                    choices = chunk_data.get("choices", [])
                    if choices and "delta" in choices[0]:
                        delta = choices[0]["delta"].get("content", "")
                        if delta:
                            yield delta

    async def __aenter__(self) -> "HebrasADKAgent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


def create_adk_config(
    base_url: str = "http://localhost:8000/v1",
    model: str = "Gemini 3.7 Flash",
    system_instruction: str | None = None,
    tools: list[Any] | None = None,
    **kwargs: Any,
) -> HebrasADKConfig:
    """Create a configured HebrasADKConfig instance.

    Args:
        base_url: hebras-ai API base URL.
        model: Model identifier.
        system_instruction: Optional system instruction prompt.
        tools: Optional list of ADK tools.
        **kwargs: Additional parameters.

    Returns:
        A configured HebrasADKConfig.
    """
    return HebrasADKConfig(
        api_base=base_url,
        model=model,
        system_instruction=system_instruction,
        tools=tools or [],
        **kwargs,
    )
