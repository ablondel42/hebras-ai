"""Tests for OpenAI-compatible type models."""
import pytest
from core.types import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    ChatMessage,
    Choice,
    ChatCompletionMessage,
    DeltaContent,
    StreamChoice,
    UsageInfo,
    ResponseFormat,
    JsonSchemaFormat,
    ModelInfo,
    ModelListResponse,
)


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest deserialization."""

    def test_basic_request(self):
        """Verify a basic OpenAI request format parses correctly."""
        data = {
            "model": "hebras-read",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
        }
        req = ChatCompletionRequest(**data)
        assert req.model == "hebras-read"
        assert len(req.messages) == 2
        assert req.messages[0].role == "system"
        assert req.messages[1].content == "Hello"
        assert req.stream is False

    def test_streaming_request(self):
        """Verify stream=True parses correctly."""
        data = {
            "model": "hebras-test",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }
        req = ChatCompletionRequest(**data)
        assert req.stream is True

    def test_request_with_response_format(self):
        """Verify response_format with json_schema parses correctly."""
        data = {
            "model": "hebras-read",
            "messages": [{"role": "user", "content": "Extract data"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
        }
        req = ChatCompletionRequest(**data)
        assert req.response_format is not None
        assert req.response_format.type == "json_schema"
        assert req.response_format.json_schema is not None
        assert req.response_format.json_schema.name == "test_schema"
        assert req.response_format.json_schema.schema_["type"] == "object"

    def test_request_defaults(self):
        """Verify default values are set correctly."""
        data = {
            "model": "hebras-read",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        req = ChatCompletionRequest(**data)
        assert req.stream is False
        assert req.n == 1
        assert req.presence_penalty == 0.0
        assert req.frequency_penalty == 0.0
        assert req.temperature is None
        assert req.workspace is None
        assert req.conversation_id is None

    def test_request_with_hebras_extensions(self):
        """Verify hebras-specific extension fields parse correctly."""
        data = {
            "model": "hebras-read",
            "messages": [{"role": "user", "content": "Hi"}],
            "workspace": "/tmp/my-project",
            "conversation_id": "abc-123",
        }
        req = ChatCompletionRequest(**data)
        assert req.workspace == "/tmp/my-project"
        assert req.conversation_id == "abc-123"


class TestChatCompletionResponse:
    """Tests for ChatCompletionResponse serialization."""

    def test_response_serialization(self):
        """Verify response matches OpenAI format."""
        resp = ChatCompletionResponse(
            model="hebras-read",
            choices=[Choice(message=ChatCompletionMessage(content="Hello!"))],
            usage=UsageInfo(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        )
        data = resp.model_dump()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["prompt_tokens"] == 5
        assert data["usage"]["total_tokens"] == 7
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")

    def test_response_has_created_timestamp(self):
        """Verify created timestamp is auto-generated."""
        resp = ChatCompletionResponse(
            model="hebras-read",
            choices=[Choice(message=ChatCompletionMessage(content="Hi"))],
            usage=UsageInfo(),
        )
        assert resp.created > 0


class TestStreamingChunk:
    """Tests for streaming chunk models."""

    def test_chunk_serialization(self):
        """Verify chunk matches OpenAI streaming format."""
        chunk = ChatCompletionChunk(
            id="chatcmpl-test123",
            created=1700000000,
            model="hebras-read",
            choices=[StreamChoice(delta=DeltaContent(content="Hello"))],
        )
        data = chunk.model_dump()
        assert data["object"] == "chat.completion.chunk"
        assert data["choices"][0]["delta"]["content"] == "Hello"
        assert data["choices"][0]["finish_reason"] is None

    def test_final_chunk_with_finish_reason(self):
        """Verify final chunk includes finish_reason."""
        chunk = ChatCompletionChunk(
            id="chatcmpl-test123",
            created=1700000000,
            model="hebras-read",
            choices=[StreamChoice(
                delta=DeltaContent(),
                finish_reason="stop",
            )],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        data = chunk.model_dump()
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["total_tokens"] == 15


class TestModelTypes:
    """Tests for model listing types."""

    def test_model_info(self):
        """Verify ModelInfo serialization."""
        model = ModelInfo(id="hebras-read", created=1700000000)
        data = model.model_dump()
        assert data["id"] == "hebras-read"
        assert data["object"] == "model"
        assert data["owned_by"] == "hebras-ai"

    def test_model_list_response(self):
        """Verify ModelListResponse format."""
        resp = ModelListResponse(data=[
            ModelInfo(id="hebras-read"),
            ModelInfo(id="hebras-test"),
        ])
        data = resp.model_dump()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
