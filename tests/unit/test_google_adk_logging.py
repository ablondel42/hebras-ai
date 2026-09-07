"""Unit tests for Google ADK logging subsystem, formatters, filters, callbacks, and self-debugging tool."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from integrations.google_adk.callbacks import (
    ADKDebugLoggingPlugin,
    adk_after_agent_callback,
    adk_after_model_callback,
    adk_after_tool_callback,
    adk_before_agent_callback,
    adk_before_model_callback,
    adk_before_tool_callback,
    adk_on_model_error_callback,
    adk_on_tool_error_callback,
)
from integrations.google_adk.logging import (
    ADKReadableFormatter,
    SubsystemFilter,
    format_adk_tree,
    get_adk_logger,
    setup_adk_logging,
)
from integrations.google_adk.tools.log_inspector import (
    _extract_recent_issues,
    inspect_execution_logs,
)


def test_adk_readable_formatter_component_tag():
    """Verify ADKReadableFormatter maps logger hierarchies to clean tags."""
    formatter = ADKReadableFormatter()

    rec_agent = logging.LogRecord(
        name="hebras.adk.agent",
        level=logging.INFO,
        pathname="agent.py",
        lineno=10,
        msg="Agent startup",
        args=(),
        exc_info=None,
    )
    formatted_agent = formatter.format(rec_agent)
    assert "[ADK.Agent]" in formatted_agent
    assert "Agent startup" in formatted_agent

    rec_tool = logging.LogRecord(
        name="hebras.adk.tools.web_search",
        level=logging.INFO,
        pathname="web_search.py",
        lineno=20,
        msg="Searching web",
        args=(),
        exc_info=None,
    )
    formatted_tool = formatter.format(rec_tool)
    assert "[ADK.Tool.WebSearch]" in formatted_tool

    rec_mem = logging.LogRecord(
        name="hebras.adk.memory.store",
        level=logging.INFO,
        pathname="store.py",
        lineno=30,
        msg="Store initialized",
        args=(),
        exc_info=None,
    )
    formatted_mem = formatter.format(rec_mem)
    assert "[ADK.Memory.Store]" in formatted_mem

    rec_mem_root = logging.LogRecord(
        name="hebras.adk.memory",
        level=logging.INFO,
        pathname="store.py",
        lineno=35,
        msg="Root memory event",
        args=(),
        exc_info=None,
    )
    formatted_mem_root = formatter.format(rec_mem_root)
    assert "[ADK.Memory]" in formatted_mem_root

    rec_model = logging.LogRecord(
        name="hebras.adk.model",
        level=logging.INFO,
        pathname="model.py",
        lineno=40,
        msg="Model call",
        args=(),
        exc_info=None,
    )
    formatted_model = formatter.format(rec_model)
    assert "[ADK.Model]" in formatted_model


def test_format_adk_tree_structure():
    """Verify format_adk_tree generates clean tree branches with duration."""
    tree = format_adk_tree(
        "Workflow Validation Completed",
        [
            ("Status", "PASSED"),
            ("Nodes", 4),
            ("Rules", ["SEC001", "LLM001"]),
        ],
        duration_ms=42.5,
    )
    lines = tree.splitlines()
    assert len(lines) == 5
    assert lines[0] == "Workflow Validation Completed"
    assert "├── Status: PASSED" in lines[1]
    assert "├── Nodes: 4" in lines[2]
    assert "├── Rules: ['SEC001', 'LLM001']" in lines[3]
    assert "└── Duration: 42.5ms" in lines[4]


def test_subsystem_filter():
    """Verify SubsystemFilter only allows records matching specific prefixes."""
    tools_filter = SubsystemFilter(("hebras.adk.tools",))

    rec_tool = logging.LogRecord("hebras.adk.tools.validator", logging.INFO, "", 0, "test", (), None)
    rec_memory = logging.LogRecord("hebras.adk.memory.store", logging.INFO, "", 0, "test", (), None)

    assert tools_filter.filter(rec_tool) is True
    assert tools_filter.filter(rec_memory) is False


def test_setup_adk_logging_file_routing(tmp_path: Path):
    """Verify setup_adk_logging creates log files and routes events correctly."""
    log_dir = tmp_path / "test_logs"
    setup_adk_logging(
        log_dir=log_dir,
        enable_console=False,
        level="DEBUG",
        force_reconfigure=True,
    )

    assert (log_dir / "adk.log").exists()
    assert (log_dir / "tools.log").exists()
    assert (log_dir / "memory.log").exists()

    logger_tool = get_adk_logger("tools.test_tool")
    logger_mem = get_adk_logger("memory.test_mem")
    logger_agent = get_adk_logger("agent")

    logger_tool.info("Test tool event")
    logger_mem.info("Test memory event")
    logger_agent.info("Test agent event")

    for h in logging.getLogger("hebras.adk").handlers:
        h.flush()

    adk_content = (log_dir / "adk.log").read_text()
    tools_content = (log_dir / "tools.log").read_text()
    mem_content = (log_dir / "memory.log").read_text()

    # Master adk.log captures all
    assert "Test tool event" in adk_content
    assert "Test memory event" in adk_content
    assert "Test agent event" in adk_content

    # tools.log captures only tools
    assert "Test tool event" in tools_content
    assert "Test memory event" not in tools_content
    assert "Test agent event" not in tools_content

    # memory.log captures only memory
    assert "Test memory event" in mem_content
    assert "Test tool event" not in mem_content
    assert "Test agent event" not in mem_content


@pytest.mark.asyncio
async def test_adk_callbacks_execution():
    """Verify lifecycle callbacks run safely without error."""
    mock_context = MagicMock()
    mock_context.agent.name = "test_agent"
    mock_context.session_id = "session-123"

    mock_request = MagicMock()
    mock_request.model = "Gemini 3.8 Flash"
    mock_request.contents = ["Prompt text"]

    mock_response = MagicMock()
    mock_response.function_calls = []

    mock_tool = MagicMock()
    mock_tool.name = "search_tool"

    # Agent callbacks
    await adk_before_agent_callback(mock_context)
    await adk_after_agent_callback(mock_context)

    # Model callbacks
    await adk_before_model_callback(mock_context, mock_request)
    await adk_after_model_callback(mock_context, mock_response)
    await adk_on_model_error_callback(mock_context, mock_request, RuntimeError("Rate limited"))

    # Tool callbacks
    await adk_before_tool_callback(mock_tool, {"query": "crm"}, mock_context)
    await adk_after_tool_callback(mock_tool, {"query": "crm"}, mock_context, {"status": "ok"})
    await adk_on_tool_error_callback(mock_tool, {"query": "crm"}, mock_context, ValueError("Invalid format"))

    # Plugin creation
    plugin = ADKDebugLoggingPlugin()
    assert plugin.name == "adk_debug_logging"
    assert plugin.before_agent_callback is not None
    assert plugin.after_tool_callback is not None


def test_inspect_execution_logs_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify inspect_execution_logs self-debugging tool functionality."""
    log_dir = tmp_path / "adk_test"
    log_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "integrations.google_adk.tools.log_inspector.DEFAULT_ADK_LOG_DIR", log_dir
    )

    sample_log = (
        "2026-09-07 10:00:00.000 [INFO] [ADK.Agent] Agent started\n"
        "2026-09-07 10:00:01.000 [WARN ] [ADK.Tool.validator] [SEC001] Plaintext secret detected in node 'Secret'\n"
        "2026-09-07 10:00:02.000 [ERROR] [ADK.Tool.workflow_proposer] Pre-save validation gate failed\n"
        "2026-09-07 10:00:03.000 [INFO] [ADK.Tool.validator] Workflow validation passed\n"
    )
    (log_dir / "adk.log").write_text(sample_log)

    # 1. Full tail inspect
    res_all = inspect_execution_logs(log_target="adk", tail_lines=10)
    assert res_all["status"] == "success"
    assert res_all["matched_lines_count"] == 4
    assert res_all["error_count"] == 1
    assert res_all["warning_count"] == 1
    assert any("SEC001" in r for r in res_all["actionable_recommendations"])

    # 2. Filter by level ERROR
    res_err = inspect_execution_logs(log_target="adk", level="ERROR")
    assert res_err["status"] == "success"
    assert res_err["matched_lines_count"] == 1
    assert "Pre-save validation gate failed" in res_err["raw_log_tail"]

    # 3. Filter by query
    res_query = inspect_execution_logs(log_target="adk", query="secret")
    assert res_query["status"] == "success"
    assert res_query["matched_lines_count"] == 1
    assert "Plaintext secret detected" in res_query["raw_log_tail"]

    # 4. Missing target file
    res_missing = inspect_execution_logs(log_target="tools")
    assert res_missing["status"] == "not_found"

    # 5. Security path traversal protection
    res_traversal = inspect_execution_logs(log_target="../../etc/passwd")
    assert res_traversal["status"] == "error"
    assert "Invalid log target" in res_traversal["message"]


def test_extract_recent_issues_heuristics():
    """Verify diagnostic recommendations for common error signatures."""
    err_lines = [
        "2026-09-07 10:00:00.000 [ERROR] [ADK.Tool.validator] SEC001 hardcoded secret sk-123456",
        "2026-09-07 10:00:01.000 [WARN ] [ADK.Tool.validator] SEC002 unauthenticated webhook detected",
        "2026-09-07 10:00:02.000 [ERROR] [ADK.Tool.validator] LLM001 external baseURL https://api.openai.com/v1 used",
        "2026-09-07 10:00:03.000 [WARN ] [ADK.Tool.validator] LEAN001 unbatched loop without splitInBatches",
        "2026-09-07 10:00:04.000 [ERROR] [ADK.Model] Connection timeout reaching http://localhost:8000/v1",
    ]
    issues, recs = _extract_recent_issues(err_lines)
    assert len(issues) == 5
    assert any("SEC001" in r for r in recs)
    assert any("SEC002" in r for r in recs)
    assert any("LLM001" in r for r in recs)
    assert any("LEAN001" in r for r in recs)
    assert any("8000" in r for r in recs)
