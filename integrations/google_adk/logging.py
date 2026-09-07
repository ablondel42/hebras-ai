"""Meaningful, human-readable logging architecture for Google ADK integration.

Provides structured tree-formatted logging routed to cleanly organized rotating
files under log/adk/ (adk.log, tools.log, memory.log).
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Default storage location: <workspace_root>/log/adk
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ADK_LOG_DIR = WORKSPACE_ROOT / "log" / "adk"

ADK_LOGGER_ROOT = "hebras.adk"


class SubsystemFilter(logging.Filter):
    """Filter that matches loggers with specific prefix names."""

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self.prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        return any(
            record.name == prefix or record.name.startswith(f"{prefix}.")
            for prefix in self.prefixes
        )


class ADKReadableFormatter(logging.Formatter):
    """Produces visually structured, easily readable logs with component tags and timestamps."""

    COMPONENT_MAP: dict[str, str] = {
        "hebras.adk": "ADK",
        "hebras.adk.agent": "ADK.Agent",
        "hebras.adk.model": "ADK.Model",
        "hebras.adk.tools": "ADK.Tool",
        "hebras.adk.tools.web_search": "ADK.Tool.WebSearch",
        "hebras.adk.tools.roi_evaluator": "ADK.Tool.ROIEval",
        "hebras.adk.tools.local_templates": "ADK.Tool.Templates",
        "hebras.adk.tools.validator": "ADK.Tool.Validator",
        "hebras.adk.tools.workflow_proposer": "ADK.Tool.Proposer",
        "hebras.adk.tools.memory": "ADK.Tool.Memory",
        "hebras.adk.tools.log_inspector": "ADK.Tool.LogInspect",
        "hebras.adk.memory": "ADK.Memory",
        "hebras.adk.memory.store": "ADK.Memory.Store",
    }

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc)
        return ct.strftime("%Y-%m-%d %H:%M:%S") + f".{int(record.msecs):03d}"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record)
        level_padded = f"{record.levelname:<5}"

        # Resolve clean component tag
        component = self.COMPONENT_MAP.get(record.name)
        if not component:
            if record.name.startswith("hebras.adk.tools."):
                sub = record.name.replace("hebras.adk.tools.", "")
                component = f"ADK.Tool.{sub.capitalize()}"
            elif record.name.startswith("hebras.adk."):
                sub = record.name.replace("hebras.adk.", "")
                component = f"ADK.{sub.capitalize()}"
            else:
                component = record.name

        msg = record.getMessage()

        # Format header line
        header = f"{timestamp} [{level_padded}] [{component}] "

        if "\n" in msg:
            # Indent subsequent lines to align with the message start
            indent = "  "
            lines = msg.splitlines()
            formatted_msg = lines[0] + "\n" + "\n".join(f"{indent}{sub_line}" for sub_line in lines[1:])
        else:
            formatted_msg = msg

        output = f"{header}{formatted_msg}"

        if record.exc_info and record.exc_info[0]:
            output += "\n" + self.formatException(record.exc_info)

        return output


def format_adk_tree(
    header: str,
    fields: list[tuple[str, Any]],
    duration_ms: float | None = None,
) -> str:
    """Format structured key-value diagnostic fields into a clean visual tree.

    Example output:
      Invoking tool: search_web_workflows
        ├── Query: 'churn recovery'
        ├── Focus: 'market_pain_and_roi'
        └── Duration: 14.2ms
    """
    items = list(fields)
    if duration_ms is not None:
        items.append(("Duration", f"{duration_ms:.1f}ms"))

    if not items:
        return header

    lines = [header]
    for i, (key, value) in enumerate(items):
        prefix = "└── " if i == len(items) - 1 else "├── "
        val_str = str(value)
        if "\n" in val_str:
            sub_lines = val_str.splitlines()
            lines.append(f"{prefix}{key}: {sub_lines[0]}")
            sub_prefix = "    " if i == len(items) - 1 else "│   "
            for sub_l in sub_lines[1:]:
                lines.append(f"{sub_prefix}{sub_l}")
        else:
            lines.append(f"{prefix}{key}: {val_str}")

    return "\n".join(lines)


def get_adk_logger(subsystem: str = "") -> logging.Logger:
    """Retrieve an ADK logger for a specific subsystem (e.g., 'tools.web_search', 'memory')."""
    if subsystem:
        return logging.getLogger(f"{ADK_LOGGER_ROOT}.{subsystem}")
    return logging.getLogger(ADK_LOGGER_ROOT)


def setup_adk_logging(
    log_dir: str | Path | None = None,
    level: str = "DEBUG",
    enable_console: bool = False,
    enable_file_handlers: bool = True,
    force_reconfigure: bool = False,
) -> Path:
    """Configure ADK loggers and rotating file handlers under log/adk/.

    Args:
        log_dir: Optional custom log directory. Defaults to <workspace>/log/adk.
        level: Minimum log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        enable_console: If True, also outputs to sys.stdout.
        enable_file_handlers: If True, writes to adk.log, tools.log, and memory.log.
        force_reconfigure: If True, clears existing handlers before adding new ones.

    Returns:
        Path to the resolved and verified log directory.
    """
    target_dir = Path(log_dir).expanduser().resolve() if log_dir else DEFAULT_ADK_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    root_adk = logging.getLogger(ADK_LOGGER_ROOT)
    resolved_level = getattr(logging, level.upper(), logging.DEBUG)
    root_adk.setLevel(resolved_level)

    # Avoid adding duplicate handlers if already configured
    if root_adk.handlers and not force_reconfigure:
        return target_dir

    if force_reconfigure:
        for handler in list(root_adk.handlers):
            handler.close()
            root_adk.removeHandler(handler)

    formatter = ADKReadableFormatter()

    if enable_file_handlers:
        # 1. Master Log: adk.log (all ADK events)
        adk_handler = RotatingFileHandler(
            target_dir / "adk.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        adk_handler.setFormatter(formatter)
        adk_handler.setLevel(resolved_level)
        root_adk.addHandler(adk_handler)

        # 2. Tools Log: tools.log (tool calls, inputs, outputs, validation gates)
        tools_handler = RotatingFileHandler(
            target_dir / "tools.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        tools_handler.setFormatter(formatter)
        tools_handler.setLevel(resolved_level)
        tools_handler.addFilter(SubsystemFilter(("hebras.adk.tools",)))
        root_adk.addHandler(tools_handler)

        # 3. Memory Log: memory.log (pattern recall, queries, persistence)
        memory_handler = RotatingFileHandler(
            target_dir / "memory.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        memory_handler.setFormatter(formatter)
        memory_handler.setLevel(resolved_level)
        memory_handler.addFilter(
            SubsystemFilter(("hebras.adk.memory", "hebras.adk.tools.memory"))
        )
        root_adk.addHandler(memory_handler)

    # Console output if explicitly requested or via env var
    env_console = os.environ.get("HEBRAS_ADK_LOG_CONSOLE", "").lower() in ("1", "true", "yes")
    if enable_console or env_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(resolved_level)
        root_adk.addHandler(console_handler)

    return target_dir
