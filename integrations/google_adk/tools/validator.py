"""Deterministic n8n validator tool for ADK agent.

Provides programmatic access to the scripts/n8n_validator.py engine for
closed-loop validation and self-correction.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.n8n_validator import N8nValidator


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
    if isinstance(workflow_json, str):
        try:
            data = json.loads(workflow_json)
        except json.JSONDecodeError as exc:
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

    if is_valid:
        diagnostics = "Workflow passed all schema, security, leanness, and local LLM constraints."
    else:
        error_msgs = [f"[{e['rule_id']}] {e['message']}" for e in errors]
        warning_msgs = [f"[{w['rule_id']}] {w['message']}" for w in warnings]
        all_issues = error_msgs + (warning_msgs if strict else [])
        diagnostics = f"Validation failed with {len(all_issues)} issue(s): " + "; ".join(all_issues)

    return {
        "valid": is_valid,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }
