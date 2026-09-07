#!/usr/bin/env python3
"""Deterministic n8n Workflow Validator & Linter CLI.

Validates n8n workflow JSON files against schema correctness, security constraints,
and leanness rules with zero third-party dependencies.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ==============================================================================
# Rule Constants & Regex Patterns
# ==============================================================================

RULE_SCH001 = "SCH001"  # Invalid JSON syntax / file read errors
RULE_SCH002 = "SCH002"  # Missing required top-level keys
RULE_SCH003 = "SCH003"  # Invalid node structure
RULE_SCH004 = "SCH004"  # Duplicate node name
RULE_SCH005 = "SCH005"  # Invalid node position
RULE_SCH006 = "SCH006"  # Dangling connection reference

RULE_SEC001 = "SEC001"  # Hardcoded plaintext secret
RULE_SEC002 = "SEC002"  # Unauthenticated webhook
RULE_SEC003 = "SEC003"  # Dangerous code execution
RULE_SEC004 = "SEC004"  # Leftover pinData test mock

RULE_LEAN001 = "LEAN001"  # Unbatched execution loop
RULE_LEAN002 = "LEAN002"  # Missing error trigger or workflow

RULE_LLM001 = "LLM001"  # External or unconfigured LLM endpoint

# Secret Detection Regexes
KNOWN_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic API Key", re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{15,}\b")),
    ("OpenAI API Key", re.compile(r"\bsk-[a-zA-Z0-9_-]{15,}\b")),
    (
        "GitHub Token",
        re.compile(r"\b(gh[pousr]_[a-zA-Z0-9]{30,}|github_pat_[a-zA-Z0-9_]{30,})\b"),
    ),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z-]{15,}\b")),
    ("AWS Access Key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google API Key", re.compile(r"\bAIzaSy[0-9A-Za-z_-]{20,}\b")),
    ("Bearer Token", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-\._~\+\/]{16,}=*)\b")),
    ("PEM Private Key", re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")),
]

SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|api[-_]?key|authorization|bearer|private[-_]?key|token)"
)
NON_SECRET_SUFFIX = re.compile(
    r"(?i)(name|header|type|label|field|id|limit|count|size|length|izer|(?<!author)ization|tokens)$"
)

EXPRESSION_PATTERN = re.compile(
    r"^=\{\{.*\}\}$|\{\{\s*\$(?:(?:env|secrets|json|node|vars|workflow|execution|item|parameter)\b|\()"
)

# Dangerous Code Execution Patterns
DANGEROUS_JS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("eval()", re.compile(r"\beval\s*\(")),
    ("Function constructor", re.compile(r"\bFunction\s*\(")),
    ("child_process module", re.compile(r"\bchild_process\b")),
    (
        "fs filesystem module",
        re.compile(
            r"(require\s*\(\s*['\"](?:node:)?fs(?:\/promises)?['\"]\s*\)|"
            r"import\s*\(\s*['\"](?:node:)?fs(?:\/promises)?['\"]\s*\)|"
            r"\bfs\.[a-zA-Z_]+)"
        ),
    ),
    ("process.exit/kill/abort", re.compile(r"\bprocess\.(?:exit|kill|abort)\b")),
    (
        "dangerous network/cluster module",
        re.compile(r"require\s*\(\s*['\"](?:node:)?(?:net|tls|dgram|cluster)['\"]\s*\)"),
    ),
]

DANGEROUS_PY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "Python os module",
        re.compile(
            r"\b(import\s+os\b|from\s+os\b|os\.(?:system|popen|spawn|exec|remove|unlink|rmdir|mkdir))\b"
        ),
    ),
    (
        "Python subprocess module",
        re.compile(r"\b(import\s+subprocess\b|from\s+subprocess\b|subprocess\.)\b"),
    ),
    ("Python eval/exec/compile", re.compile(r"\b(eval|exec|compile)\s*\(")),
    ("Python sys.exit", re.compile(r"\b(import\s+sys\b|from\s+sys\b|sys\.exit)\b")),
    ("Python dynamic import", re.compile(r"\b(__import__|importlib)\b")),
    ("Python open()", re.compile(r"\bopen\s*\(")),
]

BATCH_NODE_TYPES = {
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.loopOverItems",
}

CODE_NODE_TYPES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.function",
    "n8n-nodes-base.functionItem",
}

VALID_WEBHOOK_AUTH_TYPES: frozenset[str] = frozenset(
    {
        "headerAuth",
        "basicAuth",
        "jwtAuth",
    }
)

LLM_MODEL_NODE_TYPES: frozenset[str] = frozenset(
    {
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.openAi",
        "@n8n/n8n-nodes-langchain.lmOpenAi",
    }
)

LOCAL_LLM_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"^https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal)(?::\d+)?(?:/.*)?$",
        re.IGNORECASE,
    ),
]

# ==============================================================================
# Helper Functions
# ==============================================================================


def is_n8n_expression(value: str) -> bool:
    """Return True if string is an n8n expression or dynamic runtime reference."""
    s = value.strip()
    if s.startswith("={{"):
        return True
    if "{{" in s and "}}" in s:
        markers = (
            "$env.",
            "$secrets.",
            "$json.",
            "$vars.",
            "$node",
            "$execution",
            "$item",
            "$workflow",
            "$parameter",
            "$(",
            "$('",
            '$("',
        )
        if any(m in s for m in markers):
            return True
        if EXPRESSION_PATTERN.search(s):
            return True
    return False


def mask_secret(secret: str) -> str:
    """Mask secret value for safe diagnostic output."""
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"


def is_batch_node(node: dict[str, Any] | None) -> bool:
    """Check if a node acts as a loop controller / batch splitter."""
    if not node or not isinstance(node, dict):
        return False
    node_type = str(node.get("type", ""))
    return (
        node_type in BATCH_NODE_TYPES
        or "splitInBatches" in node_type
        or "loopOverItems" in node_type
    )


# ==============================================================================
# Data Models
# ==============================================================================


@dataclass
class ValidationIssue:
    """Represents a single validation warning or error."""

    rule_id: str
    severity: str  # "ERROR" | "WARNING"
    message: str
    node: str | None = None
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to standard dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "node": self.node,
            "location": self.location,
        }


@dataclass
class ValidationResult:
    """Represents validation findings for a single workflow."""

    file: str
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Alias for valid to maintain API compatibility."""
        return self.valid

    def to_dict(self) -> dict[str, Any]:
        """Convert result to standard dictionary."""
        return {
            "file": self.file,
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# ==============================================================================
# Validator Engine
# ==============================================================================


class N8nValidator:
    """Deterministic validator and linter for n8n workflow definitions."""

    def __init__(self, strict: bool = False, verbose: bool = False) -> None:
        self.strict = strict
        self.verbose = verbose

    def validate(
        self, data: Any, filepath: str | Path = "<memory>"
    ) -> ValidationResult:
        """Validate an in-memory parsed workflow dictionary."""
        file_str = str(filepath)
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        # Stage 1: Top-level schema structure (SCH002)
        if not isinstance(data, dict):
            errors.append(
                ValidationIssue(
                    rule_id=RULE_SCH002,
                    severity="ERROR",
                    message=f"Workflow root must be a JSON object (dict), got {type(data).__name__}",
                    location="root",
                )
            )
            return ValidationResult(file=file_str, valid=False, errors=errors, warnings=warnings)

        nodes_raw = data.get("nodes")
        if nodes_raw is None or not isinstance(nodes_raw, list):
            errors.append(
                ValidationIssue(
                    rule_id=RULE_SCH002,
                    severity="ERROR",
                    message="Workflow missing required top-level key 'nodes' (must be a list)",
                    location="nodes",
                )
            )

        connections_raw = data.get("connections")
        if connections_raw is None or not isinstance(connections_raw, dict):
            errors.append(
                ValidationIssue(
                    rule_id=RULE_SCH002,
                    severity="ERROR",
                    message="Workflow missing required top-level key 'connections' (must be a dict)",
                    location="connections",
                )
            )

        # If top-level keys are missing, abort further checks
        if errors or not isinstance(nodes_raw, list) or not isinstance(connections_raw, dict):
            return ValidationResult(file=file_str, valid=False, errors=errors, warnings=warnings)

        nodes: list[Any] = nodes_raw
        connections: dict[str, Any] = connections_raw

        # Stage 2: Node Structural Schema & Uniqueness (SCH003, SCH004, SCH005)
        node_names: set[str] = set()
        node_dict: dict[str, dict[str, Any]] = {}

        for idx, node in enumerate(nodes):
            loc_prefix = f"nodes[{idx}]"
            if not isinstance(node, dict):
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node at index {idx} must be an object (dict), got {type(node).__name__}",
                        location=loc_prefix,
                    )
                )
                continue

            # SCH003 / SCH004: name check
            name = node.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node at index {idx} missing required non-empty string 'name'",
                        location=f"{loc_prefix}.name",
                    )
                )
                node_name = f"<unnamed-node-{idx}>"
            else:
                node_name = name
                if node_name in node_names:
                    errors.append(
                        ValidationIssue(
                            rule_id=RULE_SCH004,
                            severity="ERROR",
                            message=f"Duplicate node name detected: '{node_name}'",
                            node=node_name,
                            location=f"{loc_prefix}.name",
                        )
                    )
                else:
                    node_names.add(node_name)
                    node_dict[node_name] = node

            # SCH003: id check
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id.strip():
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node '{node_name}' missing required non-empty string 'id'",
                        node=node_name,
                        location=f"{loc_prefix}.id",
                    )
                )

            # SCH003: type check
            node_type = node.get("type")
            if not isinstance(node_type, str) or not node_type.strip():
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node '{node_name}' missing required non-empty string 'type'",
                        node=node_name,
                        location=f"{loc_prefix}.type",
                    )
                )

            # SCH003: typeVersion check
            type_ver = node.get("typeVersion")
            if (
                type_ver is None
                or isinstance(type_ver, bool)
                or not isinstance(type_ver, (int, float))
            ):
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node '{node_name}' missing required numeric 'typeVersion'",
                        node=node_name,
                        location=f"{loc_prefix}.typeVersion",
                    )
                )

            # SCH003: parameters check
            params = node.get("parameters")
            if params is None or not isinstance(params, dict):
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node '{node_name}' missing required dictionary 'parameters'",
                        node=node_name,
                        location=f"{loc_prefix}.parameters",
                    )
                )

            # SCH003 / SCH005: position check
            if "position" not in node or node.get("position") is None:
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH003,
                        severity="ERROR",
                        message=f"Node '{node_name}' missing required attribute 'position'",
                        node=node_name,
                        location=f"{loc_prefix}.position",
                    )
                )
            else:
                pos = node["position"]
                if (
                    not isinstance(pos, (list, tuple))
                    or len(pos) != 2
                    or any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in pos)
                ):
                    errors.append(
                        ValidationIssue(
                            rule_id=RULE_SCH005,
                            severity="ERROR",
                            message=f"Node '{node_name}' position must be an array of 2 numbers [x, y], got {pos}",
                            node=node_name,
                            location=f"{loc_prefix}.position",
                        )
                    )

        # Stage 3: Connection Graph Integrity (SCH006)
        for src_node, outputs in connections.items():
            if src_node not in node_names:
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH006,
                        severity="ERROR",
                        message=f"Connection source node '{src_node}' does not exist in workflow nodes",
                        node=src_node,
                        location=f"connections.{src_node}",
                    )
                )

            if not isinstance(outputs, dict):
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SCH006,
                        severity="ERROR",
                        message=f"Connection mapping for node '{src_node}' must be an object (dict)",
                        node=src_node,
                        location=f"connections.{src_node}",
                    )
                )
                continue

            for conn_type, branches in outputs.items():
                if not isinstance(branches, list):
                    continue
                for branch_idx, branch in enumerate(branches):
                    if not isinstance(branch, list):
                        continue
                    for conn_idx, conn in enumerate(branch):
                        if not isinstance(conn, dict):
                            errors.append(
                                ValidationIssue(
                                    rule_id=RULE_SCH006,
                                    severity="ERROR",
                                    message=f"Connection entry from '{src_node}' must be an object",
                                    node=src_node,
                                    location=f"connections.{src_node}.{conn_type}[{branch_idx}][{conn_idx}]",
                                )
                            )
                            continue

                        target_node = conn.get("node")
                        if not isinstance(target_node, str) or not target_node.strip():
                            errors.append(
                                ValidationIssue(
                                    rule_id=RULE_SCH006,
                                    severity="ERROR",
                                    message=f"Connection from '{src_node}' missing target 'node' name",
                                    node=src_node,
                                    location=f"connections.{src_node}.{conn_type}[{branch_idx}][{conn_idx}]",
                                )
                            )
                            continue

                        if target_node not in node_names:
                            errors.append(
                                ValidationIssue(
                                    rule_id=RULE_SCH006,
                                    severity="ERROR",
                                    message=(
                                        f"Connection target node '{target_node}' referenced from "
                                        f"'{src_node}' does not exist in workflow nodes"
                                    ),
                                    node=src_node,
                                    location=f"connections.{src_node}.{conn_type}[{branch_idx}][{conn_idx}]",
                                )
                            )

        # Stage 4: Hard Security Checks (SEC001 - SEC004)
        # SEC004 - Leftover pinData
        pin_data = data.get("pinData")
        if pin_data is not None:
            if isinstance(pin_data, dict):
                if len(pin_data) > 0:
                    pinned_nodes = list(pin_data.keys())
                    errors.append(
                        ValidationIssue(
                            rule_id=RULE_SEC004,
                            severity="ERROR",
                            message=(
                                f"Workflow contains leftover pinData for node(s): {pinned_nodes}. "
                                "Pinned mock/test execution data must be cleared before deployment."
                            ),
                            location="pinData",
                        )
                    )
            elif bool(pin_data):
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_SEC004,
                        severity="ERROR",
                        message="Workflow contains non-empty pinData. Mock execution data must be cleared.",
                        location="pinData",
                    )
                )

        # Node-level security checks
        for node_name, node in node_dict.items():
            node_type = str(node.get("type", ""))
            parameters = node.get("parameters")
            if not isinstance(parameters, dict):
                parameters = {}

            # SEC001 - Hardcoded Secrets Check
            self._check_secrets(node_name, node, errors)

            # SEC002 - Unauthenticated Webhooks
            self._check_webhooks(node_name, node_type, parameters, errors)

            # SEC003 - Dangerous Code Execution
            if (
                node_type in CODE_NODE_TYPES
                or "jsCode" in parameters
                or "pythonCode" in parameters
                or "functionCode" in parameters
            ):
                self._check_dangerous_code(node_name, parameters, errors)

            # LLM001 - Local LLM API Wrapper Endpoint Check
            self._check_local_llm(node_name, node_type, parameters, errors)

        # Stage 5: Leanness Checks (LEAN001, LEAN002)
        # LEAN001 - Unbatched Loop Detection
        self._check_unbatched_loops(connections, node_dict, warnings)

        # LEAN002 - Missing Error Trigger
        self._check_error_trigger(data, node_dict, warnings)

        is_valid = len(errors) == 0
        if self.strict and len(warnings) > 0:
            is_valid = False

        return ValidationResult(
            file=file_str,
            valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    def _check_secrets(
        self,
        node_name: str,
        node: dict[str, Any],
        errors: list[ValidationIssue],
    ) -> None:
        """Scan node parameters and credentials for plaintext credentials and keys."""
        reported_locations: set[str] = set()

        def check_string_value(val: str, location: str) -> bool:
            for label, pattern in KNOWN_SECRET_PATTERNS:
                match = pattern.search(val)
                if match:
                    if label == "Bearer Token" and is_n8n_expression(val):
                        continue
                    matched_token = match.group(0)
                    masked = mask_secret(matched_token)
                    errors.append(
                        ValidationIssue(
                            rule_id=RULE_SEC001,
                            severity="ERROR",
                            message=f"Hardcoded {label} detected in node '{node_name}': {masked}",
                            node=node_name,
                            location=location,
                        )
                    )
                    reported_locations.add(location)
                    return True
            return False

        def walk(obj: Any, path: str) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    curr_path = f"{path}.{k}" if path else k
                    if SENSITIVE_KEY_PATTERN.search(k) and not NON_SECRET_SUFFIX.search(k):
                        if isinstance(v, str):
                            if not is_n8n_expression(v) and len(v.strip()) >= 6:
                                if not any(pat.search(v) for _, pat in KNOWN_SECRET_PATTERNS):
                                    masked = mask_secret(v)
                                    errors.append(
                                        ValidationIssue(
                                            rule_id=RULE_SEC001,
                                            severity="ERROR",
                                            message=(
                                                f"Sensitive parameter '{k}' in node '{node_name}' "
                                                f"contains plaintext secret: {masked}"
                                            ),
                                            node=node_name,
                                            location=curr_path,
                                        )
                                    )
                                    reported_locations.add(curr_path)
                    walk(v, curr_path)

                if "name" in obj and "value" in obj:
                    param_name = str(obj["name"])
                    param_val = obj["value"]
                    if SENSITIVE_KEY_PATTERN.search(param_name) and not NON_SECRET_SUFFIX.search(
                        param_name
                    ):
                        if (
                            isinstance(param_val, str)
                            and not is_n8n_expression(param_val)
                            and len(param_val.strip()) >= 6
                        ):
                            val_loc = f"{path}.value"
                            if val_loc not in reported_locations and not any(
                                pat.search(param_val) for _, pat in KNOWN_SECRET_PATTERNS
                            ):
                                masked = mask_secret(param_val)
                                errors.append(
                                    ValidationIssue(
                                        rule_id=RULE_SEC001,
                                        severity="ERROR",
                                        message=(
                                            f"Sensitive header/parameter '{param_name}' in node '{node_name}' "
                                            f"contains plaintext secret: {masked}"
                                        ),
                                        node=node_name,
                                        location=val_loc,
                                    )
                                )
                                reported_locations.add(val_loc)

            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    walk(item, f"{path}[{idx}]")
            elif isinstance(obj, str):
                if path not in reported_locations:
                    check_string_value(obj, path)

        parameters = node.get("parameters")
        if isinstance(parameters, (dict, list)):
            walk(parameters, f"nodes.{node_name}.parameters")

        credentials = node.get("credentials")
        if isinstance(credentials, (dict, list)):
            walk(credentials, f"nodes.{node_name}.credentials")

    def _check_webhooks(
        self,
        node_name: str,
        node_type: str,
        parameters: dict[str, Any],
        errors: list[ValidationIssue],
    ) -> None:
        """Enforce strict authentication on n8n webhook trigger nodes."""
        if node_type != "n8n-nodes-base.webhook" and not node_type.endswith(".webhook"):
            return

        auth = parameters.get("authentication")
        is_authenticated = (
            isinstance(auth, str)
            and any(auth.strip().lower() == valid.lower() for valid in VALID_WEBHOOK_AUTH_TYPES)
        )

        if not is_authenticated:
            errors.append(
                ValidationIssue(
                    rule_id=RULE_SEC002,
                    severity="ERROR",
                    message=(
                        f"Webhook node '{node_name}' has unauthenticated access "
                        f"(authentication is {auth!r}). "
                        "Must configure authentication ('headerAuth', 'basicAuth', or 'jwtAuth')."
                    ),
                    node=node_name,
                    location=f"nodes.{node_name}.parameters.authentication",
                )
            )

    def _check_dangerous_code(
        self,
        node_name: str,
        parameters: dict[str, Any],
        errors: list[ValidationIssue],
    ) -> None:
        """Scan code nodes for dangerous execution primitives in JS or Python."""
        code_keys = ("jsCode", "pythonCode", "functionCode", "code")
        for key in code_keys:
            code_val = parameters.get(key)
            if isinstance(code_val, str) and code_val:
                # Test JS patterns
                for label, pattern in DANGEROUS_JS_PATTERNS:
                    if pattern.search(code_val):
                        errors.append(
                            ValidationIssue(
                                rule_id=RULE_SEC003,
                                severity="ERROR",
                                message=(
                                    f"Dangerous code execution detected in node '{node_name}' ({key}): "
                                    f"forbidden construct '{label}'."
                                ),
                                node=node_name,
                                location=f"nodes.{node_name}.parameters.{key}",
                            )
                        )

                # Test Python patterns
                matched_py_regex = False
                for label, pattern in DANGEROUS_PY_PATTERNS:
                    if pattern.search(code_val):
                        matched_py_regex = True
                        errors.append(
                            ValidationIssue(
                                rule_id=RULE_SEC003,
                                severity="ERROR",
                                message=(
                                    f"Dangerous Python execution detected in node '{node_name}' ({key}): "
                                    f"forbidden construct '{label}'."
                                ),
                                node=node_name,
                                location=f"nodes.{node_name}.parameters.{key}",
                            )
                        )

                # Secondary Python AST check if pythonCode or key implies Python
                if not matched_py_regex and (key == "pythonCode" or "import " in code_val):
                    try:
                        tree = ast.parse(code_val)
                        for ast_node in ast.walk(tree):
                            if isinstance(ast_node, ast.Import):
                                for alias in ast_node.names:
                                    if alias.name in ("os", "subprocess", "sys", "importlib"):
                                        errors.append(
                                            ValidationIssue(
                                                rule_id=RULE_SEC003,
                                                severity="ERROR",
                                                message=(
                                                    f"Dangerous Python import '{alias.name}' detected in "
                                                    f"node '{node_name}' ({key})."
                                                ),
                                                node=node_name,
                                                location=f"nodes.{node_name}.parameters.{key}",
                                            )
                                        )
                            elif isinstance(ast_node, ast.ImportFrom):
                                mod_root = (ast_node.module or "").split(".")[0]
                                if mod_root in ("os", "subprocess", "sys", "importlib"):
                                    errors.append(
                                        ValidationIssue(
                                            rule_id=RULE_SEC003,
                                            severity="ERROR",
                                            message=(
                                                f"Dangerous Python from-import '{mod_root}' detected in "
                                                f"node '{node_name}' ({key})."
                                            ),
                                            node=node_name,
                                            location=f"nodes.{node_name}.parameters.{key}",
                                        )
                                    )
                    except SyntaxError:
                        pass

    def _check_local_llm(
        self,
        node_name: str,
        node_type: str,
        parameters: dict[str, Any],
        errors: list[ValidationIssue],
    ) -> None:
        """Validate that all LLM nodes target the local agy API wrapper (localhost:8000/v1/...)."""
        # 1. LangChain LLM chat model sub-nodes
        if node_type in LLM_MODEL_NODE_TYPES or node_type.endswith(
            (".lmChatOpenAi", ".lmOpenAi", ".openAi")
        ):
            options = parameters.get("options")
            base_url: Any = None
            if isinstance(options, dict):
                base_url = options.get("baseURL")

            if not isinstance(base_url, str) or not base_url.strip():
                errors.append(
                    ValidationIssue(
                        rule_id=RULE_LLM001,
                        severity="ERROR",
                        message=(
                            f"LLM model node '{node_name}' must configure 'options.baseURL' "
                            "pointing to the local hebras-ai agy wrapper (e.g. 'http://localhost:8000/v1' "
                            "or an expression like '={{ $env.HEBRAS_API_BASE_URL || \"http://localhost:8000/v1\" }}'), "
                            "got missing or invalid baseURL."
                        ),
                        node=node_name,
                        location=f"nodes.{node_name}.parameters.options.baseURL",
                    )
                )
            else:
                base_url_str = base_url.strip()
                if not is_n8n_expression(base_url_str):
                    is_local = any(pat.match(base_url_str) for pat in LOCAL_LLM_HOST_PATTERNS)
                    if not is_local:
                        errors.append(
                            ValidationIssue(
                                rule_id=RULE_LLM001,
                                severity="ERROR",
                                message=(
                                    f"LLM model node '{node_name}' options.baseURL must target the local "
                                    f"hebras-ai agy wrapper (e.g. 'http://localhost:8000/v1'), "
                                    f"got external or unauthorized endpoint '{base_url_str}'."
                                ),
                                node=node_name,
                                location=f"nodes.{node_name}.parameters.options.baseURL",
                            )
                        )

        # 2. Direct HTTP Request nodes invoking LLM chat completions
        elif node_type == "n8n-nodes-base.httpRequest":
            url_val = parameters.get("url")
            if isinstance(url_val, str) and not is_n8n_expression(url_val):
                url_str = url_val.strip()
                if "/v1/chat/completions" in url_str:
                    is_local = any(pat.match(url_str) for pat in LOCAL_LLM_HOST_PATTERNS)
                    if not is_local:
                        errors.append(
                            ValidationIssue(
                                rule_id=RULE_LLM001,
                                severity="ERROR",
                                message=(
                                    f"HTTP Request node '{node_name}' targets an external LLM chat completions endpoint "
                                    f"'{url_str}'. All LLM operations must target the local hebras-ai agy wrapper "
                                    "(e.g. 'http://localhost:8000/v1/chat/completions')."
                                ),
                                node=node_name,
                                location=f"nodes.{node_name}.parameters.url",
                            )
                        )

    def _check_unbatched_loops(
        self,
        connections: dict[str, Any],
        node_dict: dict[str, dict[str, Any]],
        warnings: list[ValidationIssue],
        max_cycles: int = 500,
    ) -> None:
        """Detect execution cycles lacking batch nodes in main connections using Johnson's algorithm."""
        # 1. Build directed adjacency graph from 'main' connection branches
        graph: dict[str, list[str]] = defaultdict(list)
        for src_node, outputs in connections.items():
            if not isinstance(outputs, dict):
                continue
            main_conns = outputs.get("main")
            if not isinstance(main_conns, list):
                continue
            for branch in main_conns:
                if isinstance(branch, list):
                    for conn in branch:
                        if isinstance(conn, dict):
                            tgt = conn.get("node")
                            if tgt and tgt in node_dict and src_node in node_dict:
                                if tgt not in graph[src_node]:
                                    graph[src_node].append(tgt)

        # Order nodes deterministically
        nodes: list[str] = sorted(node_dict.keys())
        node_idx: dict[str, int] = {name: i for i, name in enumerate(nodes)}
        n_nodes: int = len(nodes)

        # 2. Iterative Tarjan Strongly Connected Components (SCC) for induced subgraphs
        def get_sccs(sub_nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
            sub_set = set(sub_nodes)
            sccs: list[list[str]] = []
            idx = 0
            indices: dict[str, int] = {}
            lowlinks: dict[str, int] = {}
            on_stack: set[str] = set()
            stack: list[str] = []

            for u in sub_nodes:
                if u not in indices:
                    call_stack = [(u, 0)]
                    while call_stack:
                        v, edge_idx = call_stack[-1]
                        if edge_idx == 0:
                            indices[v] = lowlinks[v] = idx
                            idx += 1
                            stack.append(v)
                            on_stack.add(v)

                        neighbors = [w for w in adj.get(v, []) if w in sub_set]
                        advanced = False
                        for i in range(edge_idx, len(neighbors)):
                            w = neighbors[i]
                            call_stack[-1] = (v, i + 1)
                            if w not in indices:
                                call_stack.append((w, 0))
                                advanced = True
                                break
                            elif w in on_stack:
                                lowlinks[v] = min(lowlinks[v], indices[w])

                        if not advanced:
                            call_stack.pop()
                            if call_stack:
                                parent, _ = call_stack[-1]
                                lowlinks[parent] = min(lowlinks[parent], lowlinks[v])
                            if lowlinks[v] == indices[v]:
                                scc: list[str] = []
                                while True:
                                    w = stack.pop()
                                    on_stack.remove(w)
                                    scc.append(w)
                                    if w == v:
                                        break
                                sccs.append(scc)
            return sccs

        # 3. Johnson's Elementary Cycle Search with vertex blocking
        seen_unbatched_cycles: set[tuple[str, ...]] = set()
        s = 0
        while s < n_nodes:
            if len(seen_unbatched_cycles) >= max_cycles:
                break
            sub_nodes = [n for n in nodes if node_idx[n] >= s]
            sccs = get_sccs(sub_nodes, graph)
            valid_sccs = []
            for scc in sccs:
                if len(scc) > 1 or (len(scc) == 1 and scc[0] in graph.get(scc[0], [])):
                    valid_sccs.append(scc)

            if not valid_sccs:
                break

            min_scc = min(valid_sccs, key=lambda comp: min(node_idx[n] for n in comp))
            s_node = min(min_scc, key=lambda n: node_idx[n])
            s = node_idx[s_node]

            scc_set = set(min_scc)
            blocked: set[str] = set()
            b_map: dict[str, set[str]] = defaultdict(set)
            circuit_stack: list[str] = []

            def unblock(u: str) -> None:
                stack_unblock = [u]
                while stack_unblock:
                    curr = stack_unblock.pop()
                    if curr in blocked:
                        blocked.remove(curr)
                        for w in list(b_map[curr]):
                            b_map[curr].remove(w)
                            stack_unblock.append(w)

            def circuit(v: str) -> bool:
                if len(seen_unbatched_cycles) >= max_cycles:
                    return False
                found_cycle = False
                circuit_stack.append(v)
                blocked.add(v)

                for w in graph.get(v, []):
                    if w not in scc_set:
                        continue
                    if w == s_node:
                        cycle_nodes = list(circuit_stack)
                        has_batch = any(is_batch_node(node_dict.get(n)) for n in cycle_nodes)
                        if not has_batch:
                            min_idx = cycle_nodes.index(min(cycle_nodes))
                            canonical = tuple(cycle_nodes[min_idx:] + cycle_nodes[:min_idx])
                            if canonical not in seen_unbatched_cycles:
                                seen_unbatched_cycles.add(canonical)
                                path_str = " -> ".join(list(canonical) + [canonical[0]])
                                warnings.append(
                                    ValidationIssue(
                                        rule_id=RULE_LEAN001,
                                        severity="WARNING",
                                        message=(
                                            f"Unbatched loop detected: {path_str}. "
                                            "Loop does not contain a splitInBatches or loopOverItems node."
                                        ),
                                        node=canonical[0],
                                        location="connections",
                                    )
                                )
                        found_cycle = True
                        if len(seen_unbatched_cycles) >= max_cycles:
                            break
                    elif w not in blocked:
                        if circuit(w):
                            found_cycle = True
                            if len(seen_unbatched_cycles) >= max_cycles:
                                break

                if found_cycle:
                    unblock(v)
                else:
                    for w in graph.get(v, []):
                        if w in scc_set:
                            b_map[w].add(v)

                circuit_stack.pop()
                return found_cycle

            circuit(s_node)
            s += 1

    def _check_error_trigger(
        self,
        data: dict[str, Any],
        node_dict: dict[str, dict[str, Any]],
        warnings: list[ValidationIssue],
    ) -> None:
        """Verify presence of error trigger or errorWorkflow setting."""
        has_error_trigger = any(
            str(node.get("type", "")) == "n8n-nodes-base.errorTrigger"
            or "errorTrigger" in str(node.get("type", ""))
            for node in node_dict.values()
        )
        settings = data.get("settings")
        has_error_workflow = False
        if isinstance(settings, dict):
            error_wf = settings.get("errorWorkflow")
            if error_wf and (
                (isinstance(error_wf, str) and error_wf.strip())
                or isinstance(error_wf, (int, float))
            ):
                has_error_workflow = True

        if not has_error_trigger and not has_error_workflow:
            warnings.append(
                ValidationIssue(
                    rule_id=RULE_LEAN002,
                    severity="WARNING",
                    message=(
                        "Workflow lacks an errorTrigger node and has no settings.errorWorkflow configured. "
                        "Production workflows should have an error handling mechanism."
                    ),
                    location="settings.errorWorkflow",
                )
            )

    def validate_file(self, filepath: str | Path) -> ValidationResult:
        """Read and validate a workflow JSON file from disk."""
        path = Path(filepath)
        if not path.is_file():
            return ValidationResult(
                file=str(filepath),
                valid=False,
                errors=[
                    ValidationIssue(
                        rule_id=RULE_SCH001,
                        severity="ERROR",
                        message=f"File not found or not a regular file: {path}",
                        location=str(path),
                    )
                ],
            )

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return ValidationResult(
                file=str(filepath),
                valid=False,
                errors=[
                    ValidationIssue(
                        rule_id=RULE_SCH001,
                        severity="ERROR",
                        message=f"Encoding error reading JSON file: {exc}",
                        location=str(path),
                    )
                ],
            )
        except OSError as exc:
            return ValidationResult(
                file=str(filepath),
                valid=False,
                errors=[
                    ValidationIssue(
                        rule_id=RULE_SCH001,
                        severity="ERROR",
                        message=f"OS error reading file: {exc}",
                        location=str(path),
                    )
                ],
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                file=str(filepath),
                valid=False,
                errors=[
                    ValidationIssue(
                        rule_id=RULE_SCH001,
                        severity="ERROR",
                        message=f"Invalid JSON syntax at line {exc.lineno} column {exc.colno}: {exc.msg}",
                        location=f"line {exc.lineno}, col {exc.colno}",
                    )
                ],
            )

        return self.validate(data, filepath=path)

    def validate_directory(self, dirpath: str | Path) -> list[ValidationResult]:
        """Recursively validate all .json workflow files in a directory."""
        path = Path(dirpath)
        if not path.is_dir():
            return [
                ValidationResult(
                    file=str(dirpath),
                    valid=False,
                    errors=[
                        ValidationIssue(
                            rule_id=RULE_SCH001,
                            severity="ERROR",
                            message=f"Directory not found: {path}",
                            location=str(path),
                        )
                    ],
                )
            ]

        results: list[ValidationResult] = []
        for json_file in sorted(path.rglob("*.json")):
            if json_file.is_file():
                results.append(self.validate_file(json_file))
        return results


# ==============================================================================
# Public Callable Python API
# ==============================================================================


def validate_workflow(
    data: dict[str, Any], filepath: str | Path = "<memory>"
) -> ValidationResult:
    """Validate a parsed n8n workflow dictionary in memory."""
    validator = N8nValidator()
    return validator.validate(data, filepath=filepath)


def validate_file(filepath: str | Path) -> ValidationResult:
    """Validate a single n8n workflow JSON file on disk."""
    validator = N8nValidator()
    return validator.validate_file(filepath)


def validate_directory(dirpath: str | Path) -> list[ValidationResult]:
    """Recursively validate all .json workflow files in a directory."""
    validator = N8nValidator()
    return validator.validate_directory(dirpath)


# ==============================================================================
# Diagnostic Formatters & CLI
# ==============================================================================


def format_human_report(results: list[ValidationResult], verbose: bool = False) -> str:
    """Generate human-readable diagnostic report."""
    lines: list[str] = [
        "=" * 70,
        "n8n Workflow Deterministic Linter & Validator",
        "=" * 70,
    ]

    total_files = len(results)
    passed_files = 0
    total_errors = 0
    total_warnings = 0

    for res in results:
        status_str = "PASSED" if res.valid else "FAILED"
        err_count = len(res.errors)
        warn_count = len(res.warnings)
        total_errors += err_count
        total_warnings += warn_count

        if res.valid:
            passed_files += 1

        lines.append(f"\nTarget: {res.file} [{status_str}]")
        if err_count == 0 and warn_count == 0:
            lines.append("  ✓ 0 errors, 0 warnings")
        else:
            for issue in res.errors:
                loc = f" ({issue.location})" if issue.location else ""
                node_part = f" [Node: '{issue.node}']" if issue.node else ""
                lines.append(f"  [ERROR] {issue.rule_id}{node_part}{loc}: {issue.message}")
            for issue in res.warnings:
                loc = f" ({issue.location})" if issue.location else ""
                node_part = f" [Node: '{issue.node}']" if issue.node else ""
                lines.append(f"  [WARNING] {issue.rule_id}{node_part}{loc}: {issue.message}")

    lines.append("\n" + "-" * 70)
    lines.append("Summary:")
    lines.append(f"  Files checked:  {total_files}")
    lines.append(f"  Passed:         {passed_files}")
    lines.append(f"  Failed:         {total_files - passed_files}")
    lines.append(f"  Total errors:   {total_errors}")
    lines.append(f"  Total warnings: {total_warnings}")
    overall = "PASSED" if (passed_files == total_files and total_errors == 0) else "FAILED"
    lines.append(f"Overall Result:   {overall}")
    lines.append("-" * 70)

    return "\n".join(lines)


def format_json_report(results: list[ValidationResult]) -> dict[str, Any]:
    """Generate machine-readable JSON diagnostic dictionary."""
    total_files = len(results)
    passed_files = sum(1 for r in results if r.valid)
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)
    overall_valid = total_files > 0 and all(r.valid for r in results)

    return {
        "valid": overall_valid,
        "summary": {
            "files_checked": total_files,
            "passed": passed_files,
            "failed": total_files - passed_files,
            "errors": total_errors,
            "warnings": total_warnings,
        },
        "results": [r.to_dict() for r in results],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the n8n validator."""
    parser = argparse.ArgumentParser(
        description="Deterministic linter and validator for n8n workflow definitions."
    )
    parser.add_argument(
        "path",
        help="Path to an n8n workflow JSON file or a directory of workflow JSON files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured machine diagnostics in JSON format.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit code 1 if warnings are found).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed diagnostic logging.",
    )

    args = parser.parse_args(argv)
    target_path = Path(args.path)

    # Operational Check: file/directory existence
    if not target_path.exists():
        sys.stderr.write(f"Error: Target path does not exist: {target_path}\n")
        return 2

    validator = N8nValidator(strict=args.strict, verbose=args.verbose)

    if target_path.is_dir():
        results = validator.validate_directory(target_path)
        if not results:
            sys.stderr.write(f"Error: No .json workflow files found in {target_path}\n")
            return 2
    else:
        results = [validator.validate_file(target_path)]

    if args.json:
        json_output = format_json_report(results)
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(format_human_report(results, verbose=args.verbose) + "\n")

    all_valid = all(r.valid for r in results)
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
