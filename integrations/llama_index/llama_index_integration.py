"""LlamaIndex CustomLLM integration for hebras-ai."""
from typing import Any

import httpx
from llama_index.core.llms import CompletionResponse, CompletionResponseGen, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback
from pydantic import BaseModel, Field


class LlamaIndexConfig(BaseModel):
    """Configuration for LlamaIndex integration."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "Gemini 3.7 Flash"
    timeout: float = 60.0


class HebrasLLM(CustomLLM):
    """LlamaIndex CustomLLM provider wrapping hebras-ai."""

    base_url: str = Field(default="http://localhost:8000/v1")
    model_name: str = Field(default="Gemini 3.7 Flash")
    timeout: float = Field(default=60.0)

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(model_name=self.model_name, is_chat_model=True)

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"] or ""
        return CompletionResponse(text=text)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        yield self.complete(prompt, **kwargs)

    @llm_completion_callback()
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"] or ""
        return CompletionResponse(text=text)


