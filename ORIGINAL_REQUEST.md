# Original User Request

## Initial Request — 2026-09-06T20:01:04Z

Build the `n8n_architect` AI agent system in `hebras-ai` to autonomously construct, deterministically validate, and document lean and secure n8n workflows from curated templates and documentation.

Working directory: /workspaces/hebras-ai
Integrity mode: demo

## Requirements

### R1. Deterministic n8n Validator & Linter CLI
Build a standalone Python linter and validator CLI (`scripts/n8n_validator.py`) that checks n8n workflow JSON files against schema validity, security constraints (hard failure on plain-text credentials, unauthenticated webhooks, dangerous code executions like `eval` or `child_process`, and leftover `pinData`), and leanness constraints (warnings for unbatched loops and workflows lacking error triggers). Support exit code 0 for pass (or pass with warnings) and exit code 1 for hard errors, with clear human-readable and optional `--json` machine diagnostics.

### R2. Curated Knowledge Base & Seed Templates
Create a structured knowledge base in `knowledge/n8n/` with reference documentation in `knowledge/n8n/docs/` (node standards, security best practices, and `@n8n/n8n-nodes-langchain` AI nodes) and 4 production-grade seed templates in `knowledge/n8n/templates/`:
1. `secure_webhook.json`: Webhook receiver with header/signature verification, schema validation, and structured HTTP response.
2. `error_handler.json`: Sub-workflow triggered by `n8n-nodes-base.errorTrigger` formatting error context and dispatching alerts.
3. `api_batch_polling.json`: Scheduled API polling with `splitInBatches` iteration, transformation, and rate limiting.
4. `ai_agent_chain.json`: Modern n8n AI agent workflow using `@n8n/n8n-nodes-langchain` (Agent node with model, memory, and tools).

### R3. Antigravity Skill & Agent Persona
1. Create the progressive disclosure skill in `.agents/skills/n8n_builder/SKILL.md` documenting the end-to-end workflow construction procedure, template selection, and closed-loop validation steps.
2. Define the agent persona in `.agents/agents/n8n_architect/n8n_architect.md` adhering to the `hebras-ai` agent schema so it is automatically discovered by `GET /v1/agents` and usable via API and `scripts/test_cli.py`. The persona must strictly follow the autonomous self-correction loop (draft -> validate -> reflect & fix -> document).

### R4. Test Suite & Verification Harness
Create comprehensive unit tests in `tests/unit/test_n8n_validator.py` verifying:
- Clean workflows pass.
- Plaintext secrets trigger hard failures.
- Unauthenticated webhooks trigger hard failures.
- Dangerous code execution triggers hard failures.
- Missing error triggers and unbatched loops trigger warnings.
- All 4 seed templates pass validation with zero errors.
- Agent persona discovery is functional.

## Acceptance Criteria

### Validator & Security Gate
- [ ] `python scripts/n8n_validator.py --help` runs without error.
- [ ] Running the validator against a workflow with a hardcoded API key (e.g. `sk-` or bearer token) exits with non-zero code and reports a security error.
- [ ] Running the validator against an unauthenticated webhook exits with non-zero code and reports a security error.
- [ ] Running the validator against dangerous Code nodes (`eval`, `child_process`) exits with non-zero code.
- [ ] Running the validator against an unbatched loop or missing error trigger exits with code 0 and logs warnings.

### Knowledge Base & Seed Templates
- [ ] All 4 seed templates in `knowledge/n8n/templates/` exist and pass `python scripts/n8n_validator.py` with 0 errors.
- [ ] Node standards, security guidelines, and langchain node documentation exist under `knowledge/n8n/docs/`.

### Agent Persona & Skill
- [ ] Agent persona file `.agents/agents/n8n_architect/n8n_architect.md` contains valid frontmatter (`description`, `tools`, `commandExecutionPolicy`) and instructions.
- [ ] Skill file `.agents/skills/n8n_builder/SKILL.md` contains valid frontmatter (`name`, `description`) and construction runbook.
- [ ] Discoverable via `GET /v1/agents` in the FastAPI backend.

### Test Suite & Code Quality
- [ ] `pytest tests/unit/test_n8n_validator.py` passes with 100% success.
- [ ] All files follow repository standards (clean imports at module top, no inline imports, proper docstrings).
