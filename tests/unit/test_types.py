"""Tests for OpenAI-compatible type models."""
from backend.types import (
    AgentInfo,
    AgentListResponse,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    DeltaContent,
    ModelInfo,
    ModelListResponse,
    StreamChoice,
    UsageInfo,
)


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest deserialization."""

    def test_basic_request(self):
        """Verify a basic OpenAI request format parses correctly."""
        data = {
            "model": "Gemini 3.6 Flash (High)",
            "agent": "default",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
        }
        req = ChatCompletionRequest(**data)
        assert req.model == "Gemini 3.6 Flash (High)"
        assert req.agent == "default"
        assert len(req.messages) == 2
        assert req.messages[0].role == "system"
        assert req.messages[1].content == "Hello"
        assert req.stream is False

    def test_streaming_request(self):
        """Verify stream=True parses correctly."""
        data = {
            "agent": "custom-agent",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }
        req = ChatCompletionRequest(**data)
        assert req.stream is True
        assert req.agent == "custom-agent"

    def test_request_with_response_format(self):
        """Verify response_format with json_schema parses correctly."""
        data = {
            "model": "Gemini 3.6 Flash (High)",
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
            "agent": "coder",
            "model": "Claude 3.7 Sonnet",
            "messages": [{"role": "user", "content": "Hi"}],
            "workspace": "/tmp/my-project",
            "conversation_id": "abc-123",
        }
        req = ChatCompletionRequest(**data)
        assert req.agent == "coder"
        assert req.model == "Claude 3.7 Sonnet"
        assert req.workspace == "/tmp/my-project"
        assert req.conversation_id == "abc-123"


class TestChatCompletionResponse:
    """Tests for ChatCompletionResponse serialization."""

    def test_response_serialization(self):
        """Verify response matches OpenAI format."""
        resp = ChatCompletionResponse(
            model="Gemini 3.6 Flash (High)",
            agent="default",
            choices=[Choice(message=ChatCompletionMessage(content="Hello!"))],
            usage=UsageInfo(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        )
        data = resp.model_dump()
        assert data["object"] == "chat.completion"
        assert data["model"] == "Gemini 3.6 Flash (High)"
        assert data["agent"] == "default"
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
            model="Gemini 3.6 Flash (High)",
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
            model="Gemini 3.6 Flash (High)",
            agent="default",
            choices=[StreamChoice(delta=DeltaContent(content="Hello"))],
        )
        data = chunk.model_dump()
        assert data["object"] == "chat.completion.chunk"
        assert data["model"] == "Gemini 3.6 Flash (High)"
        assert data["agent"] == "default"
        assert data["choices"][0]["delta"]["content"] == "Hello"
        assert data["choices"][0]["finish_reason"] is None

    def test_final_chunk_with_finish_reason(self):
        """Verify final chunk includes finish_reason."""
        chunk = ChatCompletionChunk(
            id="chatcmpl-test123",
            created=1700000000,
            model="Gemini 3.6 Flash (High)",
            choices=[StreamChoice(
                delta=DeltaContent(),
                finish_reason="stop",
            )],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        data = chunk.model_dump()
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["total_tokens"] == 15


class TestModelAndAgentTypes:
    """Tests for model and agent listing types."""

    def test_model_info(self):
        """Verify ModelInfo serialization for foundational models."""
        model = ModelInfo(id="Gemini 3.6 Flash (High)", created=1700000000, owned_by="google")
        data = model.model_dump()
        assert data["id"] == "Gemini 3.6 Flash (High)"
        assert data["object"] == "model"
        assert data["owned_by"] == "google"

    def test_model_list_response(self):
        """Verify ModelListResponse format."""
        resp = ModelListResponse(data=[
            ModelInfo(id="Gemini 3.6 Flash (High)"),
            ModelInfo(id="Claude 3.7 Sonnet"),
        ])
        data = resp.model_dump()
        assert data["object"] == "list"
        assert len(data["data"]) == 2

    def test_agent_info(self):
        """Verify AgentInfo serialization for agent profiles."""
        agent = AgentInfo(
            id="code_reviewer",
            name="code_reviewer",
            description="Reviews code",
            tools=["read_file(*)"],
            created=1700000000,
        )
        data = agent.model_dump()
        assert data["id"] == "code_reviewer"
        assert data["object"] == "agent"
        assert data["description"] == "Reviews code"
        assert data["tools"] == ["read_file(*)"]

    def test_agent_list_response(self):
        """Verify AgentListResponse format."""
        resp = AgentListResponse(data=[
            AgentInfo(id="default", name="default"),
            AgentInfo(id="code_reviewer", name="code_reviewer"),
        ])
        data = resp.model_dump()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
