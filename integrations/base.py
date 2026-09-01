"""Shared base configuration and adapter abstractions for hebras-ai integrations."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class BaseIntegrationConfig(BaseModel):
    """Standardized configuration model for all framework integrations."""

    api_base: str = Field(
        default="http://localhost:8000/v1",
        description="hebras-ai OpenAI-compatible API base URL",
    )
    model: str = Field(
        default="Gemini 3.7 Flash",
        description="Clean LLM model name (e.g. 'Gemini 3.7 Flash', 'Claude Sonnet 4.6')",
    )
    agent: str = Field(
        default="default",
        description="agy agent persona name (e.g. 'default', 'code_writer')",
    )
    reflection: str = Field(
        default="high",
        description="Reflection/reasoning effort level ('low', 'medium', 'high')",
    )
    interactive: bool = Field(
        default=False,
        description="Whether to execute using persistent interactive PTY session",
    )
    mode: str | None = Field(
        default=None,
        description="agy execution mode (e.g. 'plan', 'accept-edits')",
    )
    dangerously_skip_permissions: bool = Field(
        default=False,
        description="Explicit opt-in to auto-approve tool execution without prompts",
    )
    timeout: float = Field(
        default=180.0,
        description="HTTP timeout in seconds",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Active multi-turn session conversation ID",
    )

    def build_payload(
        self,
        prompt: str,
        stream: bool = False,
        extra_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build an OpenAI-compatible /v1/chat/completions request payload.

        Args:
            prompt: Main user prompt message.
            stream: Whether to request SSE streaming response.
            extra_messages: Optional prior conversation messages list.

        Returns:
            Dictionary payload matching ChatCompletionRequest schema.
        """
        messages: list[dict[str, Any]] = list(extra_messages or [])
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "agent": self.agent,
            "reflection": self.reflection,
            "messages": messages,
            "interactive": self.interactive,
            "dangerously_skip_permissions": self.dangerously_skip_permissions,
        }
        if stream:
            payload["stream"] = True
        if self.mode:
            payload["mode"] = self.mode
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        return payload


class BaseHebrasAdapter(ABC):
    """Abstract base class establishing the common contract for framework adapters."""

    def __init__(self, config: BaseIntegrationConfig | None = None, **kwargs: Any) -> None:
        self.config = config or BaseIntegrationConfig(**kwargs)

    @property
    def conversation_id(self) -> str | None:
        """Active conversation ID."""
        return self.config.conversation_id

    @conversation_id.setter
    def conversation_id(self, value: str | None) -> None:
        self.config.conversation_id = value

    @abstractmethod
    def complete(self, prompt: str, **kwargs: Any) -> Any:
        """Synchronously execute a completion."""

    @abstractmethod
    async def acomplete(self, prompt: str, **kwargs: Any) -> Any:
        """Asynchronously execute a completion."""

    @abstractmethod
    def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronously stream tokens for a prompt."""
