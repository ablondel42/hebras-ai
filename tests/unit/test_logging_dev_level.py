"""Unit tests for DEV log level, JSONFormatter DEV fields, and thinking extraction."""
import json
import logging
import tempfile
from pathlib import Path

from backend.logging_config import DEV_LEVEL_NUM, JSONFormatter
from backend.turn_logger import extract_turn_thinking


class TestLoggingDevLevel:
    """Tests for DEV logging level and reflection serialization."""

    def test_dev_level_registered(self):
        """Verify DEV level has numeric value 5 and is recognized by logging."""
        assert DEV_LEVEL_NUM == 5
        assert logging.getLevelName(5) == "DEV"

    def test_json_formatter_dev_payload(self):
        """Verify JSONFormatter includes request_messages, thinking, and response at DEV level."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="backend.routes.chat",
            level=DEV_LEVEL_NUM,
            pathname=__file__,
            lineno=10,
            msg="Chat turn 1 [DEV]",
            args=(),
            exc_info=None,
        )
        record.conversation_id = "test-conv-dev-123"
        record.turn = 1
        record.agent = "default"
        record.model = "Gemini 3.7 Flash"
        record.target_model = "Gemini 3.7 Flash (High)"
        record.reflection_level = "high"
        record.mode = "streaming"
        record.request_messages = [
            {"role": "system", "content": "You are an expert."},
            {"role": "user", "content": "Explain async Python."},
        ]
        record.thinking = "Analyzing async event loop and coroutines in Python..."
        record.response = "Async in Python relies on asyncio and an event loop."
        record.duration_s = 1.450
        record.usage = {"input_tokens": 120, "output_tokens": 25, "thinking_tokens": 18, "total_tokens": 163}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "DEV"
        assert data["conversation_id"] == "test-conv-dev-123"
        assert data["turn"] == 1
        assert data["agent"] == "default"
        assert data["model"] == "Gemini 3.7 Flash"
        assert data["reflection_level"] == "high"
        assert len(data["request_messages"]) == 2
        assert data["request_messages"][0]["role"] == "system"
        assert data["request_messages"][1]["content"] == "Explain async Python."
        assert data["thinking"] == "Analyzing async event loop and coroutines in Python..."
        assert data["response"] == "Async in Python relies on asyncio and an event loop."
        assert data["duration_s"] == 1.450
        assert data["usage"]["thinking_tokens"] == 18

    def test_extract_turn_thinking(self, monkeypatch):
        """Verify extract_turn_thinking extracts thinking steps from mock transcript."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            brain_dir = Path(tmp_dir) / ".gemini" / "antigravity-cli" / "brain"
            conv_id = "mock-conv-thinking-abc"
            log_dir = brain_dir / conv_id / ".system_generated" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            transcript_file = log_dir / "transcript_full.jsonl"

            lines = [
                json.dumps({"type": "USER_INPUT", "content": "Hello"}),
                json.dumps({"type": "PLANNER_RESPONSE", "thinking": "Thinking step 1: assess intent", "tool_calls": []}),
                json.dumps({"type": "GENERIC", "content": "tool result"}),
                json.dumps({"type": "PLANNER_RESPONSE", "thinking": "Thinking step 2: generate answer", "content": "Final answer"}),
            ]
            transcript_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            monkeypatch.setattr(Path, "home", lambda: Path(tmp_dir))

            extracted = extract_turn_thinking(conv_id)
            assert "Thinking step 1: assess intent" in extracted
            assert "Thinking step 2: generate answer" in extracted
