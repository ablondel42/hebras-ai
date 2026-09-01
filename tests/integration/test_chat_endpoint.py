"""Integration tests for POST /v1/chat/completions."""
import json
from unittest.mock import AsyncMock, patch

from backend.agy_process import AgyProcessError


class TestChatCompletionsNonStreaming:
    """Tests for non-streaming chat completions."""

    async def test_basic_completion(self, client):
        """Test non-streaming chat completion returns OpenAI-compatible response with clean model."""
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

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "Gemini 3.7 Flash",
                    "agent": "default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "Gemini 3.7 Flash"
        assert data["agent"] == "default"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help?"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["usage"]["prompt_tokens"] == 100
        assert data["usage"]["completion_tokens"] == 10
        # By default high reflection is used for execution
        assert mock.call_args.kwargs["model"] == "Gemini 3.7 Flash (High)"

    async def test_reflection_selection(self, client):
        """Test passing reflection='low' correctly targets Gemini 3.7 Flash (Low)."""
        mock_result = {
            "conversation_id": "test-conv-low",
            "response": "Fast response",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "Gemini 3.7 Flash",
                    "reflection": "low",
                    "messages": [{"role": "user", "content": "Quick answer"}],
                },
            )

        assert resp.status_code == 200
        assert mock.call_args.kwargs["model"] == "Gemini 3.7 Flash (Low)"
        assert resp.json()["model"] == "Gemini 3.7 Flash"

    async def test_reasoning_effort_selection(self, client):
        """Test passing reasoning_effort='medium' targets Gemini 3.7 Flash (Medium)."""
        mock_result = {
            "conversation_id": "test-conv-med",
            "response": "Medium response",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "Gemini 3.7 Flash",
                    "reasoning_effort": "medium",
                    "messages": [{"role": "user", "content": "Medium answer"}],
                },
            )

        assert resp.status_code == 200
        assert mock.call_args.kwargs["model"] == "Gemini 3.7 Flash (Medium)"
        assert resp.json()["model"] == "Gemini 3.7 Flash"

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
                    "agent": "default",
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
                "agent": "default",
                "messages": [{"role": "system", "content": "Be helpful"}],
            },
        )
        assert resp.status_code == 400

    async def test_agy_error_returns_502(self, client):
        """Test that agy process errors return 502."""
        with patch(
            "backend.routes.chat.run_agy",
            new_callable=AsyncMock,
            side_effect=AgyProcessError("agy failed", 1, "error output"),
        ):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "agent": "default",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
        assert resp.status_code == 502

    async def test_explicit_agent_and_model(self, client):
        """Test passing both agent and model explicitly."""
        mock_result = {
            "conversation_id": "test-conv",
            "response": "ok",
            "usage": {},
        }

        with patch("backend.routes.chat.run_agy", new_callable=AsyncMock, return_value=mock_result) as mock:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "agent": "code_reviewer",
                    "model": "Claude Sonnet 4.6",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )

        assert resp.status_code == 200
        call_args = mock.call_args
        assert call_args.kwargs["agent"] == "code_reviewer"
        assert "Claude Sonnet 4.6" in call_args.kwargs["model"]
        data = resp.json()
        assert data["agent"] == "code_reviewer"
        assert data["model"] == "Claude Sonnet 4.6"

    async def test_missing_fields_defaults(self, client):
        """Test that requests omitting agent and model use settings defaults (Gemini 3.7 Flash)."""
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
        assert resp.json()["model"] == "Gemini 3.7 Flash"
        assert resp.json()["agent"] == "default"
        assert mock.call_args.kwargs["agent"] == "default"
        assert mock.call_args.kwargs["model"] == "Gemini 3.7 Flash (High)"


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
                    "agent": "default",
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

    async def test_multi_turn_streaming_continuation(self, client):
        """Test multi-turn streaming passing conversation_id across turns."""
        turn1_events = [
            {"event": "init", "conversation_id": "multi-stream-conv-999", "init": {}},
            {"event": "step_update", "step_update": {"text_delta": "Turn 1 answer"}},
            {"event": "result", "result": {"status": "SUCCESS", "usage": {}}},
        ]
        turn2_events = [
            {"event": "step_update", "step_update": {"text_delta": "Turn 2 response"}},
            {"event": "result", "result": {"status": "SUCCESS", "usage": {}}},
        ]

        # Turn 1
        async def mock_stream_turn1(*args, **kwargs):
            for e in turn1_events:
                yield e

        with patch("backend.routes.chat.stream_agy", side_effect=mock_stream_turn1):
            resp1 = await client.post(
                "/v1/chat/completions",
                json={
                    "agent": "default",
                    "messages": [{"role": "user", "content": "Turn 1 prompt"}],
                    "stream": True,
                },
            )

        assert resp1.status_code == 200
        lines1 = [json.loads(line[6:]) for line in resp1.text.strip().split("\n\n") if line.startswith("data: ") and line != "data: [DONE]"]
        conv_id = lines1[1]["system_fingerprint"]
        assert conv_id == "multi-stream-conv-999"

        # Turn 2
        async def mock_stream_turn2(*args, **kwargs):
            # Verify kwargs or args received conversation_id
            assert kwargs.get("conversation_id") == "multi-stream-conv-999"
            for e in turn2_events:
                yield e

        with patch("backend.routes.chat.stream_agy", side_effect=mock_stream_turn2):
            resp2 = await client.post(
                "/v1/chat/completions",
                json={
                    "agent": "default",
                    "conversation_id": conv_id,
                    "messages": [{"role": "user", "content": "Turn 2 prompt"}],
                    "stream": True,
                },
            )

        assert resp2.status_code == 200
        lines2 = [json.loads(line[6:]) for line in resp2.text.strip().split("\n\n") if line.startswith("data: ") and line != "data: [DONE]"]
        assert lines2[1]["choices"][0]["delta"]["content"] == "Turn 2 response"
        assert lines2[1]["system_fingerprint"] == "multi-stream-conv-999"
