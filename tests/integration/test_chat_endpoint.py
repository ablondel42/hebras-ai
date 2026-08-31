"""Integration tests for POST /v1/chat/completions."""
import json
from unittest.mock import AsyncMock, patch


class TestChatCompletionsNonStreaming:
    """Tests for non-streaming chat completions."""

    async def test_basic_completion(self, client):
        """Test non-streaming chat completion returns OpenAI-compatible response."""
        mock_result = {
            "conversation_id": "test-conv-123",
            "status": "SUCCESS",
            "response": "Hello! How can I help?",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "total_tokens": 110,
            },
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "default"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help?"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["prompt_tokens"] == 100
        assert data["usage"]["completion_tokens"] == 10

    async def test_system_message_included(self, client):
        """Test that system messages are included in the prompt."""
        mock_result = {
            "conversation_id": "test-conv-456",
            "status": "SUCCESS",
            "response": "I am helpful.",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hi"},
                    ],
                },
            )

        assert resp.status_code == 200
        # Verify system message was included in the prompt
        call_args = mock.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "You are helpful" in prompt
        assert "Hi" in prompt

    async def test_missing_user_message(self, client):
        """Test error when no user message provided."""
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "system", "content": "Be helpful"}],
            },
        )
        assert resp.status_code == 400

    async def test_agy_error_returns_502(self, client):
        """Test that agy process errors return 502."""
        from backend.agy_process import AgyProcessError

        with patch(
            "backend.routes.chat.run_agy",
            new_callable=AsyncMock,
            side_effect=AgyProcessError("agy failed", 1, "error output"),
        ):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
        assert resp.status_code == 502

    async def test_agent_extraction_from_model(self, client):
        """Test that model name is correctly mapped to agent."""
        mock_result = {
            "conversation_id": "test-conv",
            "response": "ok",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            await client.post(
                "/v1/chat/completions",
                json={
                    "model": "custom-agent",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )

        call_args = mock.call_args
        assert call_args.kwargs["agent"] == "custom-agent"

    async def test_missing_model_defaults_to_default_agent(self, client):
        """Test that requests omitting the 'model' field default to settings.agy_default_agent."""
        mock_result = {
            "conversation_id": "test-conv-raw",
            "response": "raw ok",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Raw payload test"}],
                },
            )

        assert resp.status_code == 200
        assert resp.json()["model"] == "default"
        assert mock.call_args.kwargs["agent"] == "default"


class TestChatCompletionsStreaming:
    """Tests for streaming chat completions."""

    async def test_streaming_response_format(self, client):
        """Test streaming returns SSE format with proper content type."""
        async def mock_stream(*args, **kwargs):
            yield {"event": "init", "conversation_id": "stream-conv-123", "init": {}}
            yield {"event": "step_update", "step_update": {"text_delta": "Hello"}}
            yield {"event": "step_update", "step_update": {"text_delta": " world"}}
            yield {"event": "result", "result": {"status": "SUCCESS", "usage": {}}}

        with patch("backend.routes.chat.stream_agy", side_effect=mock_stream):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE events
        lines = resp.text.strip().split("\n\n")
        events = []
        for line in lines:
            if line.startswith("data: ") and line != "data: [DONE]":
                events.append(json.loads(line[6:]))

        # Should have: role chunk, "Hello", " world", final chunk
        assert len(events) >= 3
        assert events[0]["choices"][0]["delta"]["role"] == "assistant"
        assert events[1]["choices"][0]["delta"]["content"] == "Hello"
        assert events[2]["choices"][0]["delta"]["content"] == " world"
        assert events[-1]["choices"][0]["finish_reason"] == "stop"
        assert events[1].get("system_fingerprint") == "stream-conv-123"

        # Verify [DONE] marker
        assert lines[-1] == "data: [DONE]"
