"""Google ADK integration for hebras-ai."""
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class GoogleADKConfig:
    """Configuration for Google ADK integration."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "Gemini 3.7 Flash"
    system_instruction: str | None = None
    timeout: float = 60.0


class GoogleADKAgent:
    """Minimal agent client for Google ADK workflows."""

    def __init__(self, config: GoogleADKConfig | None = None, **kwargs: Any) -> None:
        self.config = config or GoogleADKConfig(**kwargs)

    def run(self, prompt: str) -> str:
        """Run a prompt synchronously."""
        messages: list[dict[str, str]] = []
        if self.config.system_instruction:
            messages.append({"role": "system", "content": self.config.system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.config.model, "messages": messages}
        with httpx.Client(timeout=self.config.timeout) as client:
            resp = client.post(f"{self.config.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""

    async def arun(self, prompt: str) -> str:
        """Run a prompt asynchronously."""
        messages: list[dict[str, str]] = []
        if self.config.system_instruction:
            messages.append({"role": "system", "content": self.config.system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.config.model, "messages": messages}
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.post(f"{self.config.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""

