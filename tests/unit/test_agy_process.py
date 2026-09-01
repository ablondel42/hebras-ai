"""Tests for agy process command building."""
import json

from backend.agy_process import _build_command


class TestBuildCommand:
    """Tests for the _build_command helper."""

    def test_basic_command(self):
        """Verify basic command structure."""
        cmd = _build_command(
            prompt="Hello",
            agent="default",
            output_format="json",
        )
        assert cmd[0] == "agy"  # binary name from settings
        assert "--print" in cmd
        assert "Hello" in cmd
        assert "--agent" in cmd
        assert "default" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--add-dir" in cmd

    def test_command_with_json_schema(self):
        """Verify --json-schema flag is added when schema is provided."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        cmd = _build_command(
            prompt="Extract",
            agent="default",
            json_schema=schema,
        )
        assert "--json-schema" in cmd
        # Schema should be JSON-encoded
        schema_idx = cmd.index("--json-schema")
        assert json.loads(cmd[schema_idx + 1]) == schema

    def test_command_with_conversation_id(self):
        """Verify --conversation flag is added when conversation_id is provided."""
        cmd = _build_command(
            prompt="Continue",
            agent="default",
            conversation_id="abc-123",
        )
        assert "--conversation" in cmd
        conv_idx = cmd.index("--conversation")
        assert cmd[conv_idx + 1] == "abc-123"

    def test_command_without_optional_flags(self):
        """Verify optional flags are omitted when not provided."""
        cmd = _build_command(
            prompt="Hello",
            agent="default",
        )
        assert "--json-schema" not in cmd
        assert "--conversation" not in cmd

    def test_command_with_stream_json_format(self):
        """Verify stream-json output format."""
        cmd = _build_command(
            prompt="Hello",
            agent="test",
            output_format="stream-json",
        )
        assert "stream-json" in cmd

    def test_no_dangerously_skip_permissions(self):
        """Verify --dangerously-skip-permissions is NEVER included."""
        cmd = _build_command(
            prompt="Hello",
            agent="default",
        )
        assert "--dangerously-skip-permissions" not in cmd
