"""Deterministic n8n validator tool for ADK agent.

Provides programmatic access to the scripts/n8n_validator.py engine for
closed-loop validation and self-correction.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from integrations.google_adk.logging import format_adk_tree, get_adk_logger  # noqa: E402
from scripts.n8n_validator import N8nValidator  # noqa: E402

logger = get_adk_logger("tools.validator")


def validate_n8n_workflow(
    workflow_json: str | dict[str, Any], strict: bool = True
) -> dict[str, Any]:
    """Validate an n8n workflow definition against schema, security, leanness, and local LLM rules.

    Args:
        workflow_json: The workflow definition either as a JSON string or parsed dictionary.
        strict: If True, warnings (e.g. missing error triggers or unbatched loops) are treated as failures.

    Returns:
        Dictionary containing validation status ('valid': True/False), error count,
        warning count, structured lists of errors and warnings, and diagnostic guidance.
    """
    start_time = time.perf_counter()
    if isinstance(workflow_json, str):
        try:
            data = json.loads(workflow_json)
        except json.JSONDecodeError as exc:
            logger.warning(
                format_adk_tree(
                    "n8n workflow JSON decoding failed",
                    [
                        ("Status", "INVALID_JSON"),
                        ("Error", str(exc)),
                        ("Location", f"line {exc.lineno} col {exc.colno}"),
                    ],
                )
            )
            return {
                "valid": False,
                "error_count": 1,
                "warning_count": 0,
                "errors": [
                    {
                        "rule_id": "SCH001",
                        "severity": "ERROR",
                        "message": f"Invalid JSON format: {exc}",
                        "node": None,
                        "location": f"line {exc.lineno} col {exc.colno}",
                    }
                ],
                "warnings": [],
                "diagnostics": f"JSON syntax error: {exc}",
            }
    elif isinstance(workflow_json, dict):
        data = workflow_json
    else:
        logger.warning(
            f"n8n workflow validation rejected: invalid input type {type(workflow_json).__name__}"
        )
        return {
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [
                {
                    "rule_id": "SCH001",
                    "severity": "ERROR",
                    "message": f"Expected dict or JSON string, received {type(workflow_json).__name__}",
                    "node": None,
                    "location": None,
                }
            ],
            "warnings": [],
            "diagnostics": f"Expected dict or string, got {type(workflow_json).__name__}",
        }

    validator = N8nValidator(strict=strict)
    result = validator.validate(data, filepath="<memory>")

    errors = [e.to_dict() for e in result.errors]
    warnings = [w.to_dict() for w in result.warnings]

    is_valid = result.valid
    if strict and len(warnings) > 0:
        is_valid = False

    elapsed = (time.perf_counter() - start_time) * 1000.0

    if is_valid:
        diagnostics = "Workflow passed all schema, security, leanness, and local LLM constraints."
        logger.info(
            format_adk_tree(
                "n8n workflow deterministic validation passed",
                [
                    ("Status", "PASSED"),
                    ("Strict Mode", strict),
                    ("Nodes Validated", len(data.get("nodes", []))),
                    ("Errors", 0),
                    ("Warnings", len(warnings)),
                ],
                duration_ms=elapsed,
            )
        )
    else:
        error_msgs = [f"[{e['rule_id']}] {e['message']}" for e in errors]
        warning_msgs = [f"[{w['rule_id']}] {w['message']}" for w in warnings]
        all_issues = error_msgs + (warning_msgs if strict else [])
        diagnostics = f"Validation failed with {len(all_issues)} issue(s): " + "; ".join(all_issues)
        logger.warning(
            format_adk_tree(
                f"n8n workflow validation failed ({len(errors)} error(s), {len(warnings)} warning(s))",
                [
                    ("Status", "FAILED"),
                    ("Strict Mode", strict),
                    ("Error Rules", [e.get("rule_id") for e in errors]),
                    ("Warning Rules", [w.get("rule_id") for w in warnings]),
                    ("Diagnostics", diagnostics),
                ],
                duration_ms=elapsed,
            )
        )

    return {
        "valid": is_valid,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }
