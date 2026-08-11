"""OpenAI-compatible request and response Pydantic models."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: Literal["system", "user", "assistant", "tool", "developer"]
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class JsonSchemaFormat(BaseModel):
    """JSON Schema specification for structured output."""
    name: str
    description: str | None = None
    strict: bool | None = None
    schema_: dict[str, Any] = Field(alias="schema")

    model_config = {"populate_by_name": True}


class ResponseFormat(BaseModel):
    """Response format specification."""
    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: JsonSchemaFormat | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = "hebras-read"
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    n: int = 1
    stream: bool = False
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    response_format: ResponseFormat | None = None
    seed: int | None = None
    user: str | None = None
    # hebras-specific extensions
    workspace: str | None = None  # maps to --add-dir
    conversation_id: str | None = None  # explicit conversation continuation
    interactive: bool = False  # True = persistent background PTY session
    mode: str | None = None  # e.g. 'plan' or 'accept-edits'
    dangerously_skip_permissions: bool = False  # Explicit opt-in required for auto-approving tools


# ── Response Models ─────────────────────────────────────────────


class ChatCompletionMessage(BaseModel):
    """Response message from the assistant."""
    role: str = "assistant"
    content: str | None = None
    refusal: str | None = None


class Choice(BaseModel):
    """A single completion choice."""
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = "stop"


class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: UsageInfo
    system_fingerprint: str | None = None


# ── Streaming Chunk Models ──────────────────────────────────────


class DeltaContent(BaseModel):
    """Incremental content in a streaming chunk."""
    role: str | None = None
    content: str | None = None


class StreamChoice(BaseModel):
    """A streaming chunk choice."""
    index: int = 0
    delta: DeltaContent
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    usage: UsageInfo | None = None
    system_fingerprint: str | None = None


# ── Models Endpoint ─────────────────────────────────────────────


class ModelInfo(BaseModel):
    """Information about a single model."""
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "hebras-ai"


class ModelListResponse(BaseModel):
    """Response for GET /v1/models."""
    object: str = "list"
    data: list[ModelInfo]
