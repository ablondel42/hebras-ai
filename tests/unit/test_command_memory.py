"""Unit tests for CommandMemoryStore and CommandRule."""
import tempfile
from pathlib import Path
import pytest
from core.command_memory import CommandMemoryStore, CommandRule, BUILTIN_RULES


class TestCommandMemoryStore:
    """Tests for global CommandMemoryStore functionality."""

    def test_load_builtin_rules(self, tmp_path):
        """Verify built-in rules are loaded by default."""
        mem_file = tmp_path / "command_memory.json"
        store = CommandMemoryStore(memory_file_path=mem_file)

        assert len(store.rules) >= len(BUILTIN_RULES)
        # agy models should match
        rule = store.match("agy models")
        assert rule is not None
        assert rule.close_stdin is True

    def test_pattern_matching(self, tmp_path):
        """Verify regex pattern matching for CLI commands."""
        mem_file = tmp_path / "command_memory.json"
        store = CommandMemoryStore(memory_file_path=mem_file)

        # Built-in git log matching
        git_rule = store.match("git log -n 10")
        assert git_rule is not None
        assert git_rule.env_overrides.get("PAGER") == "cat"

        # Non-matching command
        no_match = store.match("ls -la")
        assert no_match is None

    def test_learn_new_hang(self, tmp_path):
        """Verify learning a new hanging command pattern persists to file."""
        mem_file = tmp_path / "command_memory.json"
        store = CommandMemoryStore(memory_file_path=mem_file)

        # Learn a new command
        learned = store.learn_hang("custom_tool interactive_prompt", reason="Hangs on stdin prompt")
        assert learned is not None
        assert learned.close_stdin is True

        # Reload store from file to ensure persistence
        store2 = CommandMemoryStore(memory_file_path=mem_file)
        match = store2.match("custom_tool interactive_prompt")
        assert match is not None
        assert match.close_stdin is True
