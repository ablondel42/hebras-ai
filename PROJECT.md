# Project: n8n_architect AI Agent System for hebras-ai

## Architecture
The `n8n_architect` system provides an autonomous, zero-trust, deterministic workflow construction, validation, and documentation capability in `hebras-ai`.
It consists of:
1. **Deterministic Validator & Linter Engine (`scripts/n8n_validator.py`)**: A zero-dependency CLI implementing a 12-rule validation suite enforcing schema correctness, strict security constraints (API keys, unauthenticated webhooks, dangerous code execution, leftover pinData), and leanness checks (unbatched loops, missing error triggers).
2. **Curated Knowledge Base & Seed Templates (`knowledge/n8n/`)**: Production documentation (`knowledge/n8n/docs/`) and 4 production-grade seed templates (`knowledge/n8n/templates/`) covering Webhook authentication, error handling sub-workflows, batch polling loops, and modern LangChain AI agent workflows.
3. **Antigravity Skill & Agent Persona (`.agents/skills/` & `.agents/agents/`)**: A progressive disclosure construction skill (`n8n_builder`) and an autonomous self-correcting agent persona (`n8n_architect`) discovered dynamically by `hebras-ai` backend (`GET /v1/agents`).
4. **Comprehensive Test Suite & Verification Harness (`tests/unit/test_n8n_validator.py`)**: Pytest test suite providing 100% verification across schema validation, security gates, leanness warnings, seed templates, agent discovery, and CLI execution.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | JSON Syntax & Top-Level Keys Validation | Validates JSON parsing and presence of `nodes` and `connections` | M1 | ORIGINAL_REQUEST § R1, Survey |
| 2 | Node Structure & Uniqueness Validation | Validates `id`, `name`, `type`, `typeVersion`, `position`, `parameters`, and duplicate name detection | M1 | ORIGINAL_REQUEST § R1, Survey |
| 3 | Connection Graph Integrity Validation | Validates that all connection source/targets reference existing nodes | M1 | Survey |
| 4 | Hardcoded Secrets Detection (SEC001) | Detects `sk-`, `ghp_`, `xoxb-`, `AKIA`, `AIzaSy`, Bearer tokens, PEM keys, sensitive key heuristics with expression exemption | M1 | ORIGINAL_REQUEST § R1, Survey |
| 5 | Unauthenticated Webhook Detection (SEC002) | Enforces authentication on `n8n-nodes-base.webhook` (`headerAuth`, `basicAuth`, etc.) | M1 | ORIGINAL_REQUEST § R1, Survey |
| 6 | Dangerous Code Execution Detection (SEC003) | Enforces sandbox safety in Code/Function nodes (blocks `eval`, `Function(`, `child_process`, `fs`, Python `os`/`subprocess`) | M1 | ORIGINAL_REQUEST § R1, Survey |
| 7 | Leftover pinData Detection (SEC004) | Rejects workflows containing non-empty `pinData` mock data | M1 | ORIGINAL_REQUEST § R1, Survey |
| 8 | Unbatched Loop Detection (LEAN001) | Emits warning on cyclic connections lacking `splitInBatches` (exit code 0) | M1 | ORIGINAL_REQUEST § R1, Survey |
| 9 | Missing Error Trigger Warning (LEAN002) | Emits warning if workflow lacks `errorTrigger` or `settings.errorWorkflow` (exit code 0) | M1 | ORIGINAL_REQUEST § R1, Survey |
| 10 | CLI Interface & Diagnostics | Supports positional path/dir, `--json` machine output, `--strict`, exit codes 0, 1, 2 | M1 | ORIGINAL_REQUEST § R1, Survey |
| 11 | Node Standards Documentation | Reference markdown for node structure, connection topologies, coordinate grid | M2 | ORIGINAL_REQUEST § R2, Survey |
| 12 | Security Guidelines Documentation | Reference markdown for credential management, webhook tiers, code isolation | M2 | ORIGINAL_REQUEST § R2, Survey |
| 13 | LangChain Nodes Documentation | Reference markdown for `@n8n/n8n-nodes-langchain` agent, model, memory, tools | M2 | ORIGINAL_REQUEST § R2, Survey |
| 14 | Seed Template: Secure Webhook | `secure_webhook.json`: Header auth, signature check, 200/401 responses, error trigger | M2 | ORIGINAL_REQUEST § R2, Survey |
| 15 | Seed Template: Error Handler | `error_handler.json`: Sub-workflow triggered by `errorTrigger`, formats error, alerts via HTTP | M2 | ORIGINAL_REQUEST § R2, Survey |
| 16 | Seed Template: Batch Polling | `api_batch_polling.json`: Scheduled trigger, `splitInBatches` loop with rate-limit wait | M2 | ORIGINAL_REQUEST § R2, Survey |
| 17 | Seed Template: AI Agent Chain | `ai_agent_chain.json`: LangChain agent, OpenAI model, memory buffer, HTTP tool | M2 | ORIGINAL_REQUEST § R2, Survey |
| 18 | Antigravity Skill: n8n_builder | `.agents/skills/n8n_builder/SKILL.md`: Progressive disclosure runbook, templates catalog, validation rules | M3 | ORIGINAL_REQUEST § R3, Survey |
| 19 | Agent Persona: n8n_architect | `.agents/agents/n8n_architect/n8n_architect.md`: Frontmatter, autonomous closed-loop protocol | M3 | ORIGINAL_REQUEST § R3, Survey |
| 20 | Dynamic Persona Discovery Integration | Dynamic discovery by `backend/routes/agents.py` and `GET /v1/agents` | M3 | ORIGINAL_REQUEST § R3, Survey |
| 21 | Test Suite: Schema & Parsing Tests | `tests/unit/test_n8n_validator.py`: JSON parsing, missing keys, invalid structures | M4 | ORIGINAL_REQUEST § R4, Survey |
| 22 | Test Suite: Security Gate Tests | Parametrized tests for secrets, webhooks, dangerous code, pinData (exit code 1) | M4 | ORIGINAL_REQUEST § R4, Survey |
| 23 | Test Suite: Leanness Warnings Tests | Tests verifying warnings for missing error triggers and unbatched loops with exit code 0 | M4 | ORIGINAL_REQUEST § R4, Survey |
| 24 | Test Suite: Seed Templates Verification | Verifies all 4 seed templates pass with 0 errors | M4 | ORIGINAL_REQUEST § R4, Survey |
| 25 | Test Suite: Agent Discovery Verification | Verifies `discover_agents()` and API discovery of `n8n_architect` | M4 | ORIGINAL_REQUEST § R4, Survey |
| 26 | Test Suite: CLI Process Invocations | Verifies CLI behavior via real subprocess execution (`--help`, `--json`, exit codes) | M4 | ORIGINAL_REQUEST § R4, Survey |
| 27 | End-to-End Verification & Verification Gate | Full verification run (pytest, CLI execution, endpoint discovery, zero error check) | M5 | Acceptance Criteria, Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Deterministic n8n Validator & Linter CLI | `scripts/n8n_validator.py` implementing 12 validation rules, CLI interface, `--json` | none | DONE |
| 2 | M2: Curated Knowledge Base & Seed Templates | `knowledge/n8n/docs/` (3 docs) and `knowledge/n8n/templates/` (4 seed templates) | M1 | DONE |
| 3 | M3: Antigravity Skill & Agent Persona | `.agents/skills/n8n_builder/SKILL.md` and `.agents/agents/n8n_architect/n8n_architect.md` | M1, M2 | DONE |
| 4 | M4: Test Suite & Verification Harness | `tests/unit/test_n8n_validator.py` covering all features & real CLI subprocess tests | M1, M2, M3 | DONE |
| 5 | M5: End-to-End Verification & Gate Hardening | Complete E2E pass, adversarial checks, forensic audit, acceptance report | M1, M2, M3, M4 | DONE |

## Interface Contracts
### Validator Engine (`scripts/n8n_validator.py`)
- Callable functions:
  - `validate_workflow(data: dict[str, Any], filepath: str | Path = "<memory>") -> ValidationResult`
  - `validate_file(filepath: str | Path) -> ValidationResult`
  - `validate_directory(dirpath: str | Path) -> list[ValidationResult]`
- Data Structures:
  - `ValidationIssue`: `rule_id: str`, `severity: str` ("ERROR" | "WARNING"), `message: str`, `node: str | None`, `location: str | None`
  - `ValidationResult`: `file: str`, `valid: bool`, `errors: list[ValidationIssue]`, `warnings: list[ValidationIssue]`
- CLI contract:
  - `python scripts/n8n_validator.py <path> [--json] [--strict] [-v]`
  - Exit 0: Passed (or passed with warnings)
  - Exit 1: Validation failed (>= 1 errors, or warnings with `--strict`)
  - Exit 2: Operational failure (file not found, invalid CLI argument)

### Agent Persona (`.agents/agents/n8n_architect/n8n_architect.md`)
- Frontmatter schema (matching `backend/routes/agents.py:_parse_frontmatter`):
  - `name: n8n_architect`
  - `description: Autonomous architect for constructing, deterministically validating, and documenting lean, secure n8n workflows.`
  - `tools:` list of tools without quotes
  - `commandExecutionPolicy: auto`

### Antigravity Skill (`.agents/skills/n8n_builder/SKILL.md`)
- Frontmatter schema:
  - `name: n8n_builder`
  - `description: ...`

## Code Layout
- `scripts/n8n_validator.py`: Standalone CLI validator script.
- `knowledge/n8n/docs/node_standards.md`: Node schema and connection specifications.
- `knowledge/n8n/docs/security_guidelines.md`: Security best practices and sandboxing rules.
- `knowledge/n8n/docs/langchain_nodes.md`: `@n8n/n8n-nodes-langchain` node references.
- `knowledge/n8n/templates/secure_webhook.json`: Seed template 1.
- `knowledge/n8n/templates/error_handler.json`: Seed template 2.
- `knowledge/n8n/templates/api_batch_polling.json`: Seed template 3.
- `knowledge/n8n/templates/ai_agent_chain.json`: Seed template 4.
- `.agents/skills/n8n_builder/SKILL.md`: Antigravity skill definition.
- `.agents/agents/n8n_architect/n8n_architect.md`: Agent persona definition.
- `tests/unit/test_n8n_validator.py`: Comprehensive test suite.
