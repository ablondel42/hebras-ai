"""Global memory system for detecting, recording, and mitigating hanging CLI commands."""
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CommandRule:
    """A rule defining a known hanging command pattern and its mitigation."""

    pattern: str  # Regex pattern matching the command line (e.g. r"^agy\s+models\b")
    description: str  # Human/AI readable reason why it hangs
    mitigation_type: str = "close_stdin"  # "close_stdin", "set_env", "add_flag", "timeout"
    env_overrides: dict[str, str] = field(default_factory=dict)
    close_stdin: bool = True
    added_args: list[str] = field(default_factory=list)
    timeout_seconds: int = 30
    hang_count: int = 1


# Pre-populated built-in rules for common CLI hangs
BUILTIN_RULES: list[CommandRule] = [
    CommandRule(
        pattern=r"^agy\s+models\b",
        description="agy models launches an interactive TUI selection prompt; requires closed stdin to return immediately.",
        mitigation_type="close_stdin",
        close_stdin=True,
        timeout_seconds=15,
    ),
    CommandRule(
        pattern=r"^git\s+(log|diff|show)\b",
        description="git log/diff/show invokes terminal pager (less) which hangs waiting for keyboard 'q'.",
        mitigation_type="set_env",
        env_overrides={"PAGER": "cat"},
        close_stdin=True,
        timeout_seconds=15,
    ),
    CommandRule(
        pattern=r"^(npm|yarn|pnpm)\s+(init|install|create)\b",
        description="Package managers can prompt interactively unless non-interactive flags are set.",
        mitigation_type="close_stdin",
        close_stdin=True,
        timeout_seconds=60,
    ),
]


class CommandMemoryStore:
    """Global persistent storage and pattern matcher for hanging CLI command rules."""

    def __init__(self, memory_file_path: str | Path | None = None):
        if memory_file_path:
            self.file_path = Path(memory_file_path).expanduser().resolve()
        else:
            # Default to global ~/.gemini/command_memory.json
            self.file_path = Path("~/.gemini/command_memory.json").expanduser().resolve()

        self.rules: list[CommandRule] = []
        self._load()

    def _load(self) -> None:
        """Load memory store from disk and merge with built-ins."""
        self.rules = [
            CommandRule(**asdict(r)) for r in BUILTIN_RULES
        ]

        if self.file_path.exists():
            try:
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                for item in data.get("rules", []):
                    try:
                        rule = CommandRule(**item)
                        # Deduplicate or update existing rule
                        existing = next((r for r in self.rules if r.pattern == rule.pattern), None)
                        if existing:
                            existing.hang_count = max(existing.hang_count, rule.hang_count)
                            existing.description = rule.description
                        else:
                            self.rules.append(rule)
                    except (TypeError, KeyError) as e:
                        logger.warning(f"Skipping malformed command rule from {self.file_path}: {e}")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load command memory store from {self.file_path}: {e}")

        # Ensure directory and initial file exist
        self.save()

    def save(self) -> None:
        """Persist current memory store rules to global disk storage."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": "1.0",
                "rules": [asdict(r) for r in self.rules],
            }
            self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Saved {len(self.rules)} rules to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save command memory store to {self.file_path}: {e}")

    def match(self, command_str: str) -> CommandRule | None:
        """Find a matching rule for a command string.

        Args:
            command_str: Full command line string or args list joined by space.

        Returns:
            Matching CommandRule or None.
        """
        clean_cmd = command_str.strip()
        for rule in self.rules:
            try:
                if re.search(rule.pattern, clean_cmd):
                    return rule
            except re.error:
                continue
        return None

    def learn_hang(
        self,
        command_str: str,
        reason: str,
        suggested_mitigation: str = "close_stdin",
    ) -> CommandRule:
        """Record a newly discovered hanging command pattern into global memory.

        Args:
            command_str: The command string that hung.
            reason: Explanation of why it hung.
            suggested_mitigation: Preferred fix strategy.

        Returns:
            The created or updated CommandRule.
        """
        parts = command_str.strip().split()
        base_cmd = parts[0] if parts else command_str
        sub_cmd = parts[1] if len(parts) > 1 and not parts[1].startswith("-") else ""

        pattern = f"^{re.escape(base_cmd)}"
        if sub_cmd:
            pattern += f"\\s+{re.escape(sub_cmd)}\\b"

        existing = self.match(command_str)
        if existing:
            existing.hang_count += 1
            existing.description = f"{reason} (hang count: {existing.hang_count})"
            self.save()
            return existing

        new_rule = CommandRule(
            pattern=pattern,
            description=f"Auto-learned: {reason}",
            mitigation_type=suggested_mitigation,
            close_stdin=True,
            timeout_seconds=20,
        )
        self.rules.append(new_rule)
        self.save()
        logger.warning(f"Learned new hanging command pattern '{pattern}' globally: {reason}")
        return new_rule
