"""Log inspection and self-debugging tool for Google ADK agent.

Allows the agent to inspect its own execution logs, diagnose tool errors,
validation failures, and exceptions, and autonomously resolve issues.
"""

from __future__ import annotations

import re
from typing import Any

from integrations.google_adk.logging import (
    DEFAULT_ADK_LOG_DIR,
    format_adk_tree,
    get_adk_logger,
)

logger = get_adk_logger("tools.log_inspector")

VALID_TARGET_MAP: dict[str, str] = {
    "adk": "adk.log",
    "tools": "tools.log",
    "memory": "memory.log",
    "all": "adk.log",
    "errors": "adk.log",
    "hebras": "../hebras.log",
}


def _extract_recent_issues(lines: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse error and warning lines to produce structured diagnostic summaries."""
    issues: list[dict[str, Any]] = []
    recommendations: list[str] = []

    error_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+\[(ERROR|WARN\s*)\]\s+\[([^\]]+)\]\s+(.*)$"
    )

    for line in lines:
        match = error_pattern.match(line)
        if match:
            ts, level, comp, msg = match.groups()
            clean_level = level.strip()
            issues.append(
                {
                    "timestamp": ts,
                    "level": clean_level,
                    "component": comp,
                    "message": msg[:200],
                }
            )

            # Heuristic actionable recommendations
            if "SEC001" in msg or "secret" in msg.lower():
                recommendations.append(
                    "SEC001 Plaintext Secret Detected: Replace raw credentials/tokens with "
                    "n8n expressions (e.g. '={{ $env.API_KEY }}' or '={{ $secrets.PASSWORD }}')."
                )
            elif "SEC002" in msg or "webhook" in msg.lower():
                recommendations.append(
                    "SEC002 Unauthenticated Webhook: Add 'authentication': 'headerAuth' or "
                    "'basicAuth' to the webhook node parameters."
                )
            elif "SEC003" in msg or "code" in msg.lower():
                recommendations.append(
                    "SEC003 Dangerous Code Execution: Remove eval, child_process, or fs from Code nodes."
                )
            elif "LLM001" in msg or "8000" in msg:
                recommendations.append(
                    "LLM001 Local LLM Host Invariant: Ensure the LLM model node options has "
                    "baseURL set to 'http://localhost:8000/v1' or 'http://127.0.0.1:8000/v1'."
                )
            elif "LEAN001" in msg or "splitinbatches" in msg.lower():
                recommendations.append(
                    "LEAN001 Unbatched Loop: Insert a splitInBatches node before looping items."
                )
            elif "LEAN002" in msg or "errortrigger" in msg.lower():
                recommendations.append(
                    "LEAN002 Missing Error Trigger: Add an n8n-nodes-base.errorTrigger node."
                )
            elif "JSONDecodeError" in msg or "SCH001" in msg:
                recommendations.append(
                    "SCH001 JSON Syntax Error: Verify workflow JSON string formatting and escaping."
                )

    # De-duplicate recommendations
    unique_recs = list(dict.fromkeys(recommendations))
    return issues[-10:], unique_recs


def inspect_execution_logs(
    log_target: str = "adk",
    level: str | None = None,
    query: str | None = None,
    tail_lines: int = 50,
) -> dict[str, Any]:
    """Inspect and analyze runtime execution logs to diagnose issues and self-correct.

    Args:
        log_target: Target log to inspect ('adk' for master trace, 'tools' for tool calls,
                    'memory' for episodic memory, 'errors' for error extraction, or 'hebras').
        level: Optional log level filter ('ERROR', 'WARNING', 'INFO', 'DEBUG').
        query: Optional case-insensitive keyword or pattern to search for (e.g. 'SEC001', 'timeout').
        tail_lines: Number of most recent matching lines to retrieve (default: 50, max: 200).

    Returns:
        Structured log inspection report containing matching lines, error summaries,
        and actionable remediation recommendations.
    """
    clean_target = log_target.strip().lower()
    if clean_target not in VALID_TARGET_MAP:
        return {
            "status": "error",
            "message": (
                f"Invalid log target: '{log_target}'. "
                f"Permitted targets are: {', '.join(sorted(VALID_TARGET_MAP.keys()))}."
            ),
        }

    filename = VALID_TARGET_MAP[clean_target]
    log_file = (DEFAULT_ADK_LOG_DIR / filename).resolve()

    # Safety check: ensure file is within the project log directory
    if not str(log_file).startswith(str(DEFAULT_ADK_LOG_DIR.parent)):
        return {
            "status": "error",
            "message": f"Invalid log target: '{log_target}' is outside permitted directory.",
        }

    if not log_file.exists():
        return {
            "status": "not_found",
            "log_target": clean_target,
            "log_file": str(log_file),
            "message": f"Log file '{log_file.name}' does not exist yet. No execution records logged.",
            "matched_lines_count": 0,
            "raw_log_tail": "",
        }

    clamped_lines = max(1, min(tail_lines, 200))

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to read log file '{log_file}': {exc}",
        }

    # Filter lines
    filtered_lines: list[str] = []
    level_filter = level.upper().strip() if level else None
    if level_filter == "WARN":
        level_filter = "WARNING"

    is_error_target = clean_target == "errors"

    for i, line in enumerate(all_lines):
        line_strip = line.strip()
        if not line_strip:
            continue

        # Check level filter
        if is_error_target:
            # Check if this line is an ERROR, WARNING, or traceback line
            is_err_line = (
                "[ERROR]" in line
                or "[WARN ]" in line
                or "[WARNING]" in line
                or line.startswith("Traceback")
                or line.startswith("  File ")
            )
            if not is_err_line:
                continue
        elif level_filter:
            if f"[{level_filter[:4]}" not in line and f"[{level_filter}" not in line:
                continue

        # Check query filter
        if query:
            if query.lower() not in line.lower():
                continue

        filtered_lines.append(line)

    tail = filtered_lines[-clamped_lines:]
    tail_text = "".join(tail)

    recent_issues, recommendations = _extract_recent_issues(tail)
    error_count = sum(1 for line_item in tail if "[ERROR]" in line_item)
    warn_count = sum(1 for line_item in tail if "[WARN" in line_item)

    # Log inspection event
    logger.debug(
        format_adk_tree(
            f"Agent inspected logs (target: {clean_target})",
            [
                ("Log File", str(log_file)),
                ("Filter Level", level_filter or "None"),
                ("Filter Query", query or "None"),
                ("Matched Lines", len(tail)),
                ("Errors Detected", error_count),
                ("Warnings Detected", warn_count),
            ],
        )
    )

    return {
        "status": "success",
        "log_target": clean_target,
        "log_file": str(log_file),
        "total_file_lines": len(all_lines),
        "matched_lines_count": len(filtered_lines),
        "returned_lines_count": len(tail),
        "error_count": error_count,
        "warning_count": warn_count,
        "recent_issues": recent_issues,
        "actionable_recommendations": recommendations,
        "diagnostics": (
            f"Retrieved {len(tail)} line(s). Found {error_count} error(s) and {warn_count} warning(s)."
            if (error_count > 0 or warn_count > 0)
            else f"No errors detected in the last {len(tail)} matching lines."
        ),
        "raw_log_tail": tail_text,
    }
