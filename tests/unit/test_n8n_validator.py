import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from backend.routes.agents import discover_agents
from scripts import n8n_validator
from scripts.n8n_validator import N8nValidator, RULE_LLM001, validate_file, validate_workflow


def _make_valid_workflow(
    with_error_trigger: bool = True,
    with_pindata: bool = True,
) -> dict[str, Any]:
    """Construct a clean, valid minimal n8n workflow for testing."""
    wf: dict[str, Any] = {
        "nodes": [
            {
                "id": "node-1",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {},
            },
            {
                "id": "node-2",
                "name": "Process Data",
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {"values": {"string": [{"name": "status", "value": "active"}]}},
            },
        ],
        "connections": {
            "Manual Trigger": {
                "main": [
                    [
                        {
                            "node": "Process Data",
                            "type": "main",
                            "index": 0,
                        }
                    ]
                ]
            }
        },
        "settings": {},
    }
    if with_error_trigger:
        wf["nodes"].append(
            {
                "id": "node-error",
                "name": "Error Trigger",
                "type": "n8n-nodes-base.errorTrigger",
                "typeVersion": 1,
                "position": [250, 500],
                "parameters": {},
            }
        )
    if with_pindata:
        wf["pinData"] = {}
    return wf


class TestValidatorSchema:
    """Tests for schema structure and JSON syntax validity."""

    def test_valid_minimal_workflow(self) -> None:
        """Assert valid minimal workflow passes validation with 0 errors and 0 warnings."""
        wf = _make_valid_workflow(with_error_trigger=True, with_pindata=True)
        result = validate_workflow(wf)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_missing_nodes_or_connections(self) -> None:
        """Assert missing 'nodes' or 'connections' root keys triggers SCH002 error."""
        # Missing 'nodes'
        res_no_nodes = validate_workflow({"connections": {}})
        assert res_no_nodes.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH002 for e in res_no_nodes.errors)

        # Missing 'connections'
        res_no_conns = validate_workflow({"nodes": []})
        assert res_no_conns.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH002 for e in res_no_conns.errors)

        # Non-dict root
        res_non_dict = validate_workflow(["invalid"])  # type: ignore
        assert res_non_dict.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH002 for e in res_non_dict.errors)

    def test_malformed_node_schema(self) -> None:
        """Assert missing node id, name, type, typeVersion, or parameters triggers SCH003."""
        # Node not a dict
        wf_bad_node = _make_valid_workflow()
        wf_bad_node["nodes"].append("not-a-dict")
        res = validate_workflow(wf_bad_node)
        assert res.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH003 for e in res.errors)

        # Node missing id
        wf_no_id = _make_valid_workflow()
        wf_no_id["nodes"][0]["id"] = ""
        res_no_id = validate_workflow(wf_no_id)
        assert res_no_id.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH003 for e in res_no_id.errors)

        # Node missing type
        wf_no_type = _make_valid_workflow()
        wf_no_type["nodes"][0]["type"] = ""
        res_no_type = validate_workflow(wf_no_type)
        assert res_no_type.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH003 for e in res_no_type.errors)

        # Node missing or invalid typeVersion
        wf_bad_ver = _make_valid_workflow()
        wf_bad_ver["nodes"][0]["typeVersion"] = True
        res_bad_ver = validate_workflow(wf_bad_ver)
        assert res_bad_ver.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH003 for e in res_bad_ver.errors)

        # Node missing parameters
        wf_no_params = _make_valid_workflow()
        wf_no_params["nodes"][0]["parameters"] = None
        res_no_params = validate_workflow(wf_no_params)
        assert res_no_params.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH003 for e in res_no_params.errors)

    def test_duplicate_node_names(self) -> None:
        """Assert duplicate node names trigger SCH004 error."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-dup",
                "name": "Process Data",  # Duplicate name of node-2
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [650, 300],
                "parameters": {},
            }
        )
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH004 for e in result.errors)

    def test_invalid_node_position(self) -> None:
        """Assert malformed position coordinates trigger SCH005 error."""
        # Position with only 1 coordinate
        wf_pos1 = _make_valid_workflow()
        wf_pos1["nodes"][0]["position"] = [100]
        res1 = validate_workflow(wf_pos1)
        assert res1.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH005 for e in res1.errors)

        # Position with non-numeric items
        wf_pos_str = _make_valid_workflow()
        wf_pos_str["nodes"][0]["position"] = ["x", "y"]
        res_str = validate_workflow(wf_pos_str)
        assert res_str.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH005 for e in res_str.errors)

        # Position with boolean
        wf_pos_bool = _make_valid_workflow()
        wf_pos_bool["nodes"][0]["position"] = [True, 200]
        res_bool = validate_workflow(wf_pos_bool)
        assert res_bool.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH005 for e in res_bool.errors)

    def test_dangling_connection_reference(self) -> None:
        """Assert connections referencing nonexistent nodes trigger SCH006 error."""
        # Nonexistent target node
        wf_bad_target = _make_valid_workflow()
        wf_bad_target["connections"]["Manual Trigger"]["main"][0][0]["node"] = "NonExistent"
        res_target = validate_workflow(wf_bad_target)
        assert res_target.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH006 for e in res_target.errors)

        # Nonexistent source node
        wf_bad_src = _make_valid_workflow()
        wf_bad_src["connections"]["GhostNode"] = {"main": [[{"node": "Process Data"}]]}
        res_src = validate_workflow(wf_bad_src)
        assert res_src.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH006 for e in res_src.errors)

    def test_invalid_json_syntax(self, tmp_path: Path) -> None:
        """Assert corrupted JSON syntax triggers SCH001 error."""
        corrupted = tmp_path / "corrupted.json"
        corrupted.write_text('{"nodes": [ malformed JSON content ', encoding="utf-8")
        result = validate_file(corrupted)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH001 for e in result.errors)

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Assert missing file on disk triggers SCH001 error."""
        missing = tmp_path / "does_not_exist.json"
        result = validate_file(missing)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SCH001 for e in result.errors)


class TestSecurityPlaintextSecrets:
    """Tests for detection of hardcoded plaintext secrets and expression exemptions."""

    @pytest.mark.parametrize(
        "secret_val,label",
        [
            ("sk-1234567890abcdefABCDEF", "OpenAI API Key"),
            ("sk-ant-api03-1234567890abcdefABCDEF", "Anthropic API Key"),
            ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "GitHub Token"),
            ("xoxb-1234567890-1234567890-abcdefghijklmnop", "Slack Token"),
            ("AKIAIOSFODNN7EXAMPLE", "AWS Access Key"),
            ("AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "Google API Key"),
            ("Bearer abcdef1234567890_token_value", "Bearer Token"),
            (
                "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASC\n-----END PRIVATE KEY-----",
                "PEM Private Key",
            ),
        ],
    )
    def test_secret_patterns(self, secret_val: str, label: str) -> None:
        """Assert known secret tokens anywhere in parameters trigger SEC001 error."""
        wf = _make_valid_workflow()
        wf["nodes"][1]["parameters"]["apiKey"] = secret_val
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC001 for e in result.errors)

    @pytest.mark.parametrize(
        "param_key,secret_val",
        [
            ("password", "SuperSecretPassword123"),
            ("api_key", "custom_secret_api_key_val"),
            ("secret", "top_secret_application_value"),
            ("authorization", "Basic dXNlcm5hbWU6cGFzc3dvcmQ="),
            ("private_key", "MIIEvgIBADANBgkqhkiG9w0BAQEFAASC"),
        ],
    )
    def test_sensitive_keys_flagged(self, param_key: str, secret_val: str) -> None:
        """Assert sensitive parameter keys containing plaintext strings trigger SEC001."""
        wf = _make_valid_workflow()
        wf["nodes"][1]["parameters"][param_key] = secret_val
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC001 for e in result.errors)

    def test_nested_header_secrets_flagged(self) -> None:
        """Assert secrets nested in header lists trigger SEC001."""
        wf = _make_valid_workflow()
        wf["nodes"][1]["parameters"] = {
            "headerParameters": {
                "parameters": [{"name": "X-API-Key", "value": "hardcoded_secret_token_12345"}]
            }
        }
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC001 for e in result.errors)

    @pytest.mark.parametrize(
        "expression",
        [
            "={{ $env.OPENAI_API_KEY }}",
            "={{ $json.api_token }}",
            "{{ $('AuthNode').item.json.token }}",
            "{{ $secrets.DATABASE_PASSWORD }}",
            "={{ $parameter['apiKey'] }}",
            "Bearer {{ $env.BEARER_TOKEN }}",
            "{{ $vars.API_SECRET }}",
        ],
    )
    def test_expression_secrets_not_flagged(self, expression: str) -> None:
        """Assert dynamic n8n expressions referencing environment or json are exempt from SEC001."""
        wf = _make_valid_workflow()
        wf["nodes"][1]["parameters"]["apiKey"] = expression
        wf["nodes"][1]["parameters"]["password"] = expression
        result = validate_workflow(wf)
        assert result.valid is True
        assert not any(e.rule_id == n8n_validator.RULE_SEC001 for e in result.errors)

    def test_non_secret_suffixes_not_flagged(self) -> None:
        """Assert parameters ending in non-secret suffixes are not falsely flagged."""
        wf = _make_valid_workflow()
        wf["nodes"][1]["parameters"] = {
            "apiKeyName": "X-Auth-Token",
            "tokenType": "Bearer",
            "secretLabel": "Production Secret",
            "tokenLimit": 5000,
        }
        result = validate_workflow(wf)
        assert result.valid is True
        assert not any(e.rule_id == n8n_validator.RULE_SEC001 for e in result.errors)


class TestSecurityWebhooks:
    """Tests for webhook authentication enforcement."""

    def test_unauthenticated_webhook_omitted_fails(self) -> None:
        """Assert webhook with omitted authentication triggers SEC002 error."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-wh",
                "name": "Webhook Receiver",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 300],
                "parameters": {
                    "path": "test-webhook",
                    "httpMethod": "POST",
                },
            }
        )
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC002 for e in result.errors)

    def test_unauthenticated_webhook_none_fails(self) -> None:
        """Assert webhook with authentication='none' triggers SEC002 error."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-wh",
                "name": "Webhook Receiver",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 300],
                "parameters": {
                    "path": "test-webhook",
                    "httpMethod": "POST",
                    "authentication": "none",
                },
            }
        )
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC002 for e in result.errors)

    @pytest.mark.parametrize("auth_type", ["headerAuth", "basicAuth", "jwtAuth"])
    def test_authenticated_webhook_passes(self, auth_type: str) -> None:
        """Assert webhook with valid authentication passes SEC002 check."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-wh",
                "name": "Webhook Receiver",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 300],
                "parameters": {
                    "path": "test-webhook",
                    "httpMethod": "POST",
                    "authentication": auth_type,
                },
            }
        )
        result = validate_workflow(wf)
        assert not any(e.rule_id == n8n_validator.RULE_SEC002 for e in result.errors)


class TestSecurityDangerousCode:
    """Tests for dangerous execution primitives in Code/Function nodes."""

    @pytest.mark.parametrize(
        "snippet,label",
        [
            ("const x = eval('2 + 2');", "eval()"),
            ("const fn = Function('return 1');", "Function constructor"),
            ("const cp = require('child_process'); cp.execSync('ls');", "child_process"),
            ("const fs = require('fs');", "require fs"),
            ("await import('node:fs');", "import fs"),
            ("process.exit(1);", "process.exit"),
            ("process.kill(100);", "process.kill"),
        ],
    )
    def test_dangerous_javascript_primitives(self, snippet: str, label: str) -> None:
        """Assert dangerous JS primitives trigger SEC003 error."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-code",
                "name": "Custom Code",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [650, 300],
                "parameters": {
                    "jsCode": snippet,
                },
            }
        )
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC003 for e in result.errors)

    @pytest.mark.parametrize(
        "snippet,label",
        [
            ("import os\nos.system('rm -rf /')", "import os"),
            ("import subprocess\nsubprocess.run(['ls'])", "import subprocess"),
            ("from os import system\nsystem('whoami')", "from os import"),
            ("from subprocess import Popen", "from subprocess import"),
            ("eval('1 + 1')", "eval()"),
            ("exec('a = 1')", "exec()"),
            ("import sys\nsys.exit(0)", "sys.exit"),
            ("open('/etc/shadow', 'r')", "open()"),
        ],
    )
    def test_dangerous_python_primitives(self, snippet: str, label: str) -> None:
        """Assert dangerous Python primitives trigger SEC003 error."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-code",
                "name": "Python Code",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [650, 300],
                "parameters": {
                    "pythonCode": snippet,
                },
            }
        )
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC003 for e in result.errors)

    def test_safe_code_transforms_pass(self) -> None:
        """Assert safe JavaScript and Python transforms pass SEC003 check."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-safe-js",
                "name": "Safe JS",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [650, 300],
                "parameters": {
                    "jsCode": (
                        "return items.map(item => ({\n"
                        "  json: { ...item.json, processed: true, count: item.json.count * 2 }\n"
                        "}));"
                    ),
                },
            }
        )
        wf["nodes"].append(
            {
                "id": "node-safe-py",
                "name": "Safe Python",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [850, 300],
                "parameters": {
                    "pythonCode": (
                        "out = []\n"
                        "for item in _input.all():\n"
                        "    val = item['json'].get('value', 0)\n"
                        "    out.append({'json': {'value': val * 2}})\n"
                        "return out"
                    ),
                },
            }
        )
        result = validate_workflow(wf)
        assert not any(e.rule_id == n8n_validator.RULE_SEC003 for e in result.errors)

    def test_benign_comments_not_flagged(self) -> None:
        """Assert benign words in comments do not trigger SEC003."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-code",
                "name": "Comment Code",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [650, 300],
                "parameters": {
                    "jsCode": ("// evaluating whether to transform output\nreturn items;"),
                },
            }
        )
        result = validate_workflow(wf)
        assert not any(e.rule_id == n8n_validator.RULE_SEC003 for e in result.errors)


class TestSecurityPinData:
    """Tests for detection of leftover mock execution data (pinData)."""

    def test_pindata_with_data_fails(self) -> None:
        """Assert non-empty pinData triggers SEC004 error."""
        wf = _make_valid_workflow()
        wf["pinData"] = {
            "Manual Trigger": [{"json": {"mock_user_id": 42, "email": "test@example.com"}}]
        }
        result = validate_workflow(wf)
        assert result.valid is False
        assert any(e.rule_id == n8n_validator.RULE_SEC004 for e in result.errors)

    def test_empty_pindata_or_absent_passes(self) -> None:
        """Assert empty pinData ({}) or omitted pinData passes SEC004 check."""
        # Empty pinData dict
        wf_empty = _make_valid_workflow(with_pindata=True)
        wf_empty["pinData"] = {}
        res_empty = validate_workflow(wf_empty)
        assert not any(e.rule_id == n8n_validator.RULE_SEC004 for e in res_empty.errors)

        # Omitted pinData key
        wf_omitted = _make_valid_workflow(with_pindata=False)
        assert "pinData" not in wf_omitted
        res_omitted = validate_workflow(wf_omitted)
        assert not any(e.rule_id == n8n_validator.RULE_SEC004 for e in res_omitted.errors)


class TestLeannessWarnings:
    """Tests for leanness warnings (LEAN001, LEAN002) with exit code 0."""

    def test_missing_error_trigger_emits_warning(self) -> None:
        """Assert workflow lacking errorTrigger emits LEAN002 warning but stays valid."""
        wf = _make_valid_workflow(with_error_trigger=False)
        result = validate_workflow(wf)
        assert result.valid is True
        assert len(result.errors) == 0
        assert any(w.rule_id == n8n_validator.RULE_LEAN002 for w in result.warnings)

    def test_error_trigger_present_no_warning(self) -> None:
        """Assert workflow with errorTrigger node emits 0 LEAN002 warnings."""
        wf = _make_valid_workflow(with_error_trigger=True)
        result = validate_workflow(wf)
        assert not any(w.rule_id == n8n_validator.RULE_LEAN002 for w in result.warnings)

    def test_settings_error_workflow_no_warning(self) -> None:
        """Assert workflow with settings.errorWorkflow configured emits 0 LEAN002 warnings."""
        wf = _make_valid_workflow(with_error_trigger=False)
        wf["settings"] = {"errorWorkflow": "error-subworkflow-uuid-123"}
        result = validate_workflow(wf)
        assert not any(w.rule_id == n8n_validator.RULE_LEAN002 for w in result.warnings)

    def test_unbatched_loop_emits_warning(self) -> None:
        """Assert circular loop lacking splitInBatches emits LEAN001 warning but stays valid."""
        wf = _make_valid_workflow(with_error_trigger=True)
        # Create cycle: Process Data connects back to Manual Trigger
        wf["connections"]["Process Data"] = {
            "main": [
                [
                    {
                        "node": "Manual Trigger",
                        "type": "main",
                        "index": 0,
                    }
                ]
            ]
        }
        result = validate_workflow(wf)
        assert result.valid is True
        assert len(result.errors) == 0
        assert any(w.rule_id == n8n_validator.RULE_LEAN001 for w in result.warnings)

    def test_batched_loop_no_warning(self) -> None:
        """Assert circular loop controlled by splitInBatches node emits 0 LEAN001 warnings."""
        wf = _make_valid_workflow(with_error_trigger=True)
        # Add splitInBatches node
        wf["nodes"].append(
            {
                "id": "node-batch",
                "name": "Batch Splitter",
                "type": "n8n-nodes-base.splitInBatches",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {"batchSize": 10},
            }
        )
        wf["connections"] = {
            "Manual Trigger": {"main": [[{"node": "Batch Splitter", "type": "main", "index": 0}]]},
            "Batch Splitter": {"main": [[{"node": "Process Data", "type": "main", "index": 0}]]},
            "Process Data": {"main": [[{"node": "Batch Splitter", "type": "main", "index": 0}]]},
        }
        result = validate_workflow(wf)
        assert result.valid is True
        assert len(result.errors) == 0
        assert not any(w.rule_id == n8n_validator.RULE_LEAN001 for w in result.warnings)

    def test_strict_mode_rejects_warnings(self) -> None:
        """Assert strict mode marks workflow as invalid when warnings are present."""
        validator = N8nValidator(strict=True)
        wf = _make_valid_workflow(with_error_trigger=False)  # Triggers LEAN002
        result = validator.validate(wf)
        assert result.valid is False
        assert len(result.warnings) > 0


class TestSeedTemplates:
    """Tests asserting all production seed templates pass validation with 0 errors and 0 warnings."""

    @pytest.mark.parametrize(
        "template_name",
        [
            "secure_webhook.json",
            "error_handler.json",
            "api_batch_polling.json",
            "ai_agent_chain.json",
        ],
    )
    def test_all_seed_templates_pass(self, template_name: str) -> None:
        """Assert seed template in knowledge/n8n/templates/ is valid with 0 errors and 0 warnings."""
        template_path = Path("knowledge/n8n/templates") / template_name
        assert template_path.is_file(), f"Seed template file not found: {template_path}"

        result = validate_file(template_path)
        assert result.valid is True, f"Template {template_name} failed validation: {result.errors}"
        assert len(result.errors) == 0, f"Template {template_name} has errors: {result.errors}"
        assert len(result.warnings) == 0, (
            f"Template {template_name} has warnings: {result.warnings}"
        )


class TestAgentPersona:
    """Tests verifying n8n_architect persona discovery and REST API endpoint."""

    def test_persona_discovery_in_backend(self) -> None:
        """Assert discover_agents() dynamically discovers n8n_architect with valid attributes."""
        agents = discover_agents()
        agent_map = {a.id: a for a in agents}
        assert "n8n_architect" in agent_map, "n8n_architect agent not discovered"

        agent = agent_map["n8n_architect"]
        assert agent.name == "n8n_architect"
        assert agent.description is not None
        assert "Autonomous architect" in agent.description
        assert isinstance(agent.tools, list)
        assert "read_file(*)" in agent.tools
        assert "write_to_file(*)" in agent.tools
        assert "replace_file_content(*)" in agent.tools
        assert "run_command(*)" in agent.tools
        assert agent.command_execution_policy == "auto"

    async def test_persona_via_agents_endpoint(self, client: Any) -> None:
        """Assert GET /v1/agents returns 200 OK with n8n_architect in data list."""
        resp = await client.get("/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"

        agent_map = {a["id"]: a for a in data["data"]}
        assert "n8n_architect" in agent_map, "n8n_architect not returned in /v1/agents"

        agent = agent_map["n8n_architect"]
        assert agent["name"] == "n8n_architect"
        assert "Autonomous architect" in agent["description"]
        assert "read_file(*)" in agent["tools"]
        assert agent["command_execution_policy"] == "auto"


class TestCliInterface:
    """Tests executing scripts/n8n_validator.py via subprocess."""

    def test_cli_help_flag(self) -> None:
        """Assert --help exits 0 and displays CLI usage instructions."""
        res = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        assert "--help" in res.stdout or "-h" in res.stdout
        assert "--json" in res.stdout
        assert "--strict" in res.stdout

    def test_cli_valid_workflow_exit_zero(self, tmp_path: Path) -> None:
        """Assert valid workflow file exits with code 0."""
        valid_file = tmp_path / "valid.json"
        valid_file.write_text(
            json.dumps(_make_valid_workflow(with_error_trigger=True, with_pindata=True)),
            encoding="utf-8",
        )
        res = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(valid_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        assert "PASSED" in res.stdout

    def test_cli_invalid_workflow_exit_one(self, tmp_path: Path) -> None:
        """Assert invalid workflow file exits with code 1."""
        invalid_wf = _make_valid_workflow()
        invalid_wf["nodes"][1]["parameters"]["apiKey"] = "sk-1234567890abcdefABCDEF"
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text(json.dumps(invalid_wf), encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(invalid_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 1
        assert "FAILED" in res.stdout

    def test_cli_nonexistent_file_exit_two(self, tmp_path: Path) -> None:
        """Assert nonexistent file path exits with code 2 and prints error to stderr."""
        missing = tmp_path / "missing_workflow.json"
        res = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(missing)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2
        assert "does not exist" in res.stderr

    def test_cli_json_output_structure(self, tmp_path: Path) -> None:
        """Assert --json produces structured machine diagnostics matching expected schema."""
        valid_file = tmp_path / "valid.json"
        valid_file.write_text(
            json.dumps(_make_valid_workflow(with_error_trigger=True, with_pindata=True)),
            encoding="utf-8",
        )
        res = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(valid_file), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        parsed = json.loads(res.stdout)
        assert "valid" in parsed
        assert parsed["valid"] is True
        assert "summary" in parsed
        assert parsed["summary"]["files_checked"] == 1
        assert parsed["summary"]["passed"] == 1
        assert parsed["summary"]["failed"] == 0
        assert parsed["summary"]["errors"] == 0
        assert "results" in parsed
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["valid"] is True
        assert parsed["results"][0]["errors"] == []
        assert parsed["results"][0]["warnings"] == []

    def test_cli_strict_flag_exits_one_on_warnings(self, tmp_path: Path) -> None:
        """Assert --strict causes workflows with warnings to exit with code 1."""
        warn_wf = _make_valid_workflow(with_error_trigger=False)
        warn_file = tmp_path / "warn.json"
        warn_file.write_text(json.dumps(warn_wf), encoding="utf-8")

        # Without --strict: exit 0
        res_normal = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(warn_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_normal.returncode == 0

        # With --strict: exit 1
        res_strict = subprocess.run(
            [sys.executable, "scripts/n8n_validator.py", str(warn_file), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_strict.returncode == 1
        assert "FAILED" in res_strict.stdout


class TestLocalLlmRule:
    """Tests verifying RULE_LLM001: local Antigravity API wrapper enforcement."""

    def test_lm_chat_openai_with_local_base_url_passes(self) -> None:
        """Assert lmChatOpenAi with http://localhost:8000/v1 passes LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-model",
                "name": "Local Agy Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1.2,
                "position": [360, 520],
                "parameters": {
                    "model": "Gemini 3.7 Flash",
                    "options": {
                        "baseURL": "http://localhost:8000/v1",
                    },
                },
            }
        )
        res = validate_workflow(wf)
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 0

    def test_lm_chat_openai_with_env_expression_passes(self) -> None:
        """Assert lmChatOpenAi with an expression for baseURL passes LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-model",
                "name": "Local Agy Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1.2,
                "position": [360, 520],
                "parameters": {
                    "model": "Gemini 3.7 Flash",
                    "options": {
                        "baseURL": "={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}",
                    },
                },
            }
        )
        res = validate_workflow(wf)
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 0

    def test_lm_chat_openai_missing_base_url_fails(self) -> None:
        """Assert lmChatOpenAi without baseURL fails LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-model",
                "name": "Unconfigured Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1.2,
                "position": [360, 520],
                "parameters": {
                    "model": "gpt-4o-mini",
                    "options": {},
                },
            }
        )
        res = validate_workflow(wf)
        assert res.valid is False
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 1
        assert "must configure 'options.baseURL'" in llm_errors[0].message

    def test_lm_chat_openai_external_base_url_fails(self) -> None:
        """Assert lmChatOpenAi with external baseURL (api.openai.com) fails LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-model",
                "name": "External Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1.2,
                "position": [360, 520],
                "parameters": {
                    "model": "gpt-4o",
                    "options": {
                        "baseURL": "https://api.openai.com/v1",
                    },
                },
            }
        )
        res = validate_workflow(wf)
        assert res.valid is False
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 1
        assert "must target the local hebras-ai agy wrapper" in llm_errors[0].message

    def test_http_request_external_chat_completions_fails(self) -> None:
        """Assert httpRequest targeting external chat completions endpoint fails LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-http",
                "name": "External Chat Completion",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [450, 300],
                "parameters": {
                    "method": "POST",
                    "url": "https://api.openai.com/v1/chat/completions",
                },
            }
        )
        res = validate_workflow(wf)
        assert res.valid is False
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 1
        assert "targets an external LLM chat completions endpoint" in llm_errors[0].message

    def test_http_request_local_chat_completions_passes(self) -> None:
        """Assert httpRequest targeting local chat completions endpoint passes LLM001."""
        wf = _make_valid_workflow()
        wf["nodes"].append(
            {
                "id": "node-http",
                "name": "Local Chat Completion",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [450, 300],
                "parameters": {
                    "method": "POST",
                    "url": "http://localhost:8000/v1/chat/completions",
                },
            }
        )
        res = validate_workflow(wf)
        llm_errors = [e for e in res.errors if e.rule_id == RULE_LLM001]
        assert len(llm_errors) == 0
