"""LlamaIndex CustomLLM integration for hebras-ai.

Subclasses CustomLLM from llama_index.core.llms to allow LlamaIndex to treat
hebras-ai (and its agy backend) as a remote LLM provider.
"""
import json
import logging
from typing import Any, Optional

import httpx
from pydantic import Field

from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.llms import (
    CompletionResponse,
    CompletionResponseGen,
    CustomLLM,
    LLMMetadata,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.llms.function_calling import FunctionCallingLLM

logger = logging.getLogger(__name__)


class HebrasLLM(CustomLLM, FunctionCallingLLM):
    """LlamaIndex CustomLLM provider wrapping hebras-ai.

    Appears as a standard LLM and FunctionCallingLLM to LlamaIndex pipelines and
    agents while delegating to hebras-ai (which manages persistent agy sessions under the hood).
    """

    api_base: str = Field(default="http://localhost:8000/v1", description="hebras-ai API base URL")
    agent: str = Field(default="read", description="agy agent name (e.g. read, code_writer)")
    interactive: bool = Field(default=False, description="Whether to use persistent interactive PTY session")
    mode: Optional[str] = Field(default=None, description="agy execution mode (e.g. plan, accept-edits)")
    dangerously_skip_permissions: bool = Field(default=False, description="Explicit opt-in to auto-approve tool execution")
    context_window: int = Field(default=131072, description="Context window size")
    num_output: int = Field(default=4096, description="Max generation tokens")
    model_name: str = Field(default="hebras-read", description="Model name identifier")
    conversation_id: Optional[str] = Field(default=None, description="Active session conversation ID")
    timeout: float = Field(default=180.0, description="HTTP timeout in seconds")

    def __init__(self, set_as_default: bool = False, **data: Any):
        super().__init__(**data)
        self.model_name = f"hebras-{'interactive-' if self.interactive else ''}{self.agent}"
        if set_as_default:
            from llama_index.core import Settings
            Settings.llm = self

    def _build_payload(self, prompt: str, stream: bool = False) -> dict[str, Any]:
        """Build request payload."""
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
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

    def _prepare_chat_with_tools(
        self,
        tools: Any,
        user_msg: Any = None,
        chat_history: Any = None,
        verbose: bool = False,
        allow_parallel_tool_calls: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare chat payload for LlamaIndex FunctionCallingLLM agent workflows."""
        messages = list(chat_history or [])
        if user_msg:
            if isinstance(user_msg, str):
                messages.append(ChatMessage(role="user", content=user_msg))
            else:
                messages.append(user_msg)
        return {"messages": messages, "tools": tools}

    def get_tool_calls_from_response(
        self,
        response: Any,
        error_on_no_tool_call: bool = False,
    ) -> list[Any]:
        """Extract tool calls from LLM response for LlamaIndex FunctionCallingLLM interface.

        Note: Currently a stub returning [] so LlamaIndex FunctionAgent accepts HebrasLLM.
        """
        if error_on_no_tool_call:
            raise ValueError("No tool calls found in response.")
        return []

    @property
    def metadata(self) -> LLMMetadata:
        """LLM metadata required by LlamaIndex."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model_name,
        )

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Synchronous completion call."""
        payload = self._build_payload(prompt)

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.api_base}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"] or ""
        if "system_fingerprint" in data:
            self.conversation_id = data["system_fingerprint"]

        return CompletionResponse(text=text, raw=data)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        """Streaming completion call."""
        payload = self._build_payload(prompt, stream=True)

        yielded_any = False
        current_text = ""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{self.api_base}/chat/completions", json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        chunk_data = json.loads(data_str)
                        if "system_fingerprint" in chunk_data and chunk_data["system_fingerprint"]:
                            self.conversation_id = chunk_data["system_fingerprint"]

                        choices = chunk_data.get("choices", [])
                        if choices and "delta" in choices[0]:
                            delta = choices[0]["delta"].get("content", "")
                            if delta:
                                current_text += delta
                                yielded_any = True
                                yield CompletionResponse(text=current_text, delta=delta, raw=chunk_data)
        except Exception as e:
            logger.warning(f"Streaming failed, falling back to sync completion: {e}")

        if not yielded_any:
            res = self.complete(prompt, **kwargs)
            yield res

    @llm_completion_callback()
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Async completion call."""
        payload = self._build_payload(prompt)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.api_base}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"] or ""
        if "system_fingerprint" in data:
            self.conversation_id = data["system_fingerprint"]

        return CompletionResponse(text=text, raw=data)


if __name__ == "__main__":
    import asyncio
    from llama_index.core.agent.workflow import FunctionAgent

    llm = HebrasLLM(
        api_base="http://localhost:8000/v1",
        agent="read",
        interactive=True,
    )

    agent = FunctionAgent(
        llm=llm,
        system_prompt="You are a helpful assistant powered by hebras-ai.",
    )

    async def main():
        print("Running LlamaIndex FunctionAgent with HebrasLLM...")
        response = await agent.run(user_msg="What is 1234 * 4567?")
        print("Agent Response:", str(response))

    asyncio.run(main())
