---
name: n8n-builder
description: >
  This skill should be used when the user wants to "build an n8n workflow",
  "create n8n flow", "generate n8n JSON", "validate n8n workflow",
  "lint n8n JSON", "fix n8n security", or needs guidance on n8n workflow
  patterns, nodes, error triggers, batch polling, webhooks, or AI agents.
metadata:
  author: hebras-ai
  version: 1.0.0
---

# n8n Workflow Construction & Deterministic Validation Skill (`n8n-builder`)

This skill defines the end-to-end engineering methodology for constructing, deterministically validating, hardening, and documenting production-grade n8n workflows within the `hebras-ai` ecosystem.

---

## 1. Architectural Philosophy & Principles

All n8n workflows generated or maintained under this skill must adhere to four immutable principles:

1. **Zero-Trust Security**:
   - Never embed plaintext credentials, API tokens (`sk-`, `ghp_`, `Bearer`), private keys, or passwords.
   - Credentials must strictly use n8n encrypted credential references (`credentials: { <type>: { id: "...", name: "..." } }`) or runtime environment variable expressions (`={{ $env.VARIABLE_NAME }}`).
   - Webhook triggers must enforce authentication (`headerAuth`, `basicAuth`, or HMAC signature verification).
   - Code/Function nodes must never use dangerous primitives (`eval`, `child_process`, `Function(`, `require('fs')`, `process.exit`).
   - Mock test payloads (`pinData`) must be emptied (`{}`) prior to deployment or export.

2. **Deterministic Validation First**:
   - No workflow is complete until it passes `python scripts/n8n_validator.py <workflow.json>` with 0 errors.
   - Validation is not an afterthought; it is a mandatory gate in the autonomous generation loop.

3. **Lean & Resilient Topology**:
   - Any loop over recurring items or paginated endpoints must be governed by `n8n-nodes-base.splitInBatches` with rate-limiting pauses (`n8n-nodes-base.wait`).
   - Workflows must handle failures gracefully, either via an explicit `n8n-nodes-base.errorTrigger` node or via `settings.errorWorkflow`.

4. **Progressive Disclosure**:
   - Tier 1: 6-Phase Construction Runbook (below).
   - Tier 2: Template Catalog Reference Table (Section 3).
   - Tier 3: Technical Reference Docs (Section 4).

5. **Local LLM Wrapper Invariant (`LLM001`)**:
   - All LLM reasoning and generation within n8n workflows MUST route strictly through the local Antigravity API wrapper (`http://localhost:8000/v1/...`).
   - Never configure workflows to call external proprietary LLM endpoints (`api.openai.com`, etc.).
   - When using `@n8n/n8n-nodes-langchain.lmChatOpenAi`, always set `options.baseURL` to `'http://localhost:8000/v1'` (or `={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}`) and select models discovered from `hebras-ai` (`Gemini 3.7 Flash`, `Claude Sonnet 4.6`, `GPT-OSS 120B`).
   - When using `n8n-nodes-base.httpRequest` for LLM completions, target `http://localhost:8000/v1/chat/completions`.

---

## 2. 6-Phase Workflow Construction Runbook

When designing or modifying an n8n workflow, execute the following six phases in sequence:

```
[ Phase 1: Requirements ]
          │
          ▼
[ Phase 2: Template Scaffolding ]
          │
          ▼
[ Phase 3: Node Hardening ]
          │
          ▼
[ Phase 4: Deterministic Validation ] ◄───────┐
          │                                  │ (Reflect & Fix)
          ├────────── Fail (Errors > 0) ─────┘
          ▼ Pass (Errors == 0)
[ Phase 5: Closed-Loop Remediation Check ]
          │
          ▼
[ Phase 6: Documentation & Export ]
```

### Phase 1: Requirement Analysis & Topology Selection
1. **Identify Entry Point / Trigger**:
   - Webhook trigger -> Use authenticated webhook archetype (`secure_webhook.json`).
   - Schedule / Cron -> Use batch polling archetype (`api_batch_polling.json`).
   - Event / Queue -> Use standard message receiver.
   - AI Reasoning / Chat -> Use LangChain AI Agent archetype (`ai_agent_chain.json`).
   - Error Handler -> Use error trigger archetype (`error_handler.json`).
2. **Determine Ingestion & Transformation Requirements**:
   - Determine input payload schemas, required headers, and filtering logic.
   - Plan data transformations using standard `n8n-nodes-base.set` or safe pure JS in `n8n-nodes-base.code`.
3. **Plan Failure Modes & Error Handling**:
   - Identify external API failure points.
   - Determine if an in-workflow `errorTrigger` or global error sub-workflow is needed.

### Phase 2: Template Scaffolding
Rather than authoring raw JSON from scratch, select the closest seed template from `knowledge/n8n/templates/`:

| Seed Template | Path | Primary Purpose |
| :--- | :--- | :--- |
| **Secure Webhook** | `knowledge/n8n/templates/secure_webhook.json` | Authenticated webhook entrypoint, header verification, 200/401 responses, and error handler. |
| **Error Handler** | `knowledge/n8n/templates/error_handler.json` | Dedicated sub-workflow triggered by `errorTrigger`, extracting error metadata and alerting. |
| **Batch Polling** | `knowledge/n8n/templates/api_batch_polling.json` | Periodic API polling with `splitInBatches` iteration, transformation, rate limiting, and loop cycle. |
| **AI Agent Chain** | `knowledge/n8n/templates/ai_agent_chain.json` | Modern `@n8n/n8n-nodes-langchain` agent with Chat model, Window Buffer Memory, and HTTP tool. |

Copy the chosen template to your target destination (e.g. `workflows/<target_name>.json`) as the initial baseline.

### Phase 3: Node Configuration & Hardening
1. **Set Canonical Top-Level Properties**:
   ```json
   {
     "name": "Production Descriptive Name",
     "nodes": [...],
     "connections": {...},
     "settings": {
       "executionOrder": "v1"
     },
     "pinData": {},
     "meta": {
       "templateCredsSetupCompleted": true
     }
   }
   ```
2. **Assign Unique IDs & Descriptive Names**:
   - Node `id`: Standard UUID v4 or short alphanumeric string (e.g. `uuid.uuid4()`).
   - Node `name`: Clear functional name (e.g. `"Validate HMAC Signature"`, `"Filter Inactive Users"`).
   - Ensure all names within `nodes` are unique (`SCH004`).
3. **Establish Proper Canvas Coordinates (`position`)**:
   - Position must be `[x, y]` with integer coordinates (`SCH005`).
   - Recommended layout: Horizontal progression `x += 220`, parallel branches vertical offset `y += 180`.
4. **Wire Connections Accurately**:
   - Every connection target node name must exist in the `nodes` array (`SCH006`).
   - For standard nodes: `connections[SourceNode]["main"][0] = [{ "node": TargetNode, "type": "main", "index": 0 }]`.
   - For LangChain sub-nodes: Connect to AI ports (`ai_languageModel`, `ai_memory`, `ai_tool`).
5. **Enforce Security Hardening Rules**:
   - Webhooks: Set `authentication` to `"headerAuth"`, `"basicAuth"`, or implement cryptographic verification. Never leave `authentication: "none"` (`SEC002`).
   - Secrets: Never put raw keys in `parameters`. Use `credentials` mapping or expressions (`={{ $env.SECRET_KEY }}`) (`SEC001`).
   - Code Nodes: Use only safe pure array mapping (`items.map(item => ({ json: ... }))`). Never use `eval`, `child_process`, `fs`, `process` (`SEC003`).
   - Pinned Data: Purge all mock data by setting `"pinData": {}` (`SEC004`).

### Phase 4: Deterministic Validation CLI
Execute the deterministic validator CLI to inspect the workflow:
```bash
python scripts/n8n_validator.py <path_to_workflow.json> --json
```

Evaluate the exit code:
- **Exit Code 0**: Workflow is valid! (Warnings may be present; review them).
- **Exit Code 1**: Hard validation failure. Immediate remediation required.
- **Exit Code 2**: Operational failure (file not found or bad CLI flags).

### Phase 5: Reflection & Closed-Loop Remediation
If errors > 0, inspect the `errors` array from the JSON output and execute the corresponding remediation:

| Rule ID | Violation | Root Cause | Automated Remediation Action |
| :--- | :--- | :--- | :--- |
| `SCH001` | Syntax Error | Malformed JSON syntax | Fix JSON parsing error (trailing commas, unbalanced braces). |
| `SCH002` | Missing Keys | Missing `nodes` or `connections` | Add missing top-level keys: `"nodes": []`, `"connections": {}`. |
| `SCH003` | Node Schema | Missing `id`, `name`, `type`, `parameters` | Populate missing mandatory fields on the flagged node. |
| `SCH004` | Duplicate Name | Multiple nodes share the same `name` | Rename duplicate nodes to unique descriptive names. |
| `SCH005` | Node Position | `position` not `[x, y]` numbers | Reset `position` to `[100, 200]` or valid coordinates. |
| `SCH006` | Dangling Conn | Connection targets non-existent node | Update connection mapping to reference valid existing node names. |
| `SEC001` | Plaintext Secret | Raw API key / token / password detected | Replace literal with credential reference or `={{ $env.VAR_NAME }}`. |
| `SEC002` | Unauth Webhook | Webhook missing auth or `none` | Add `"authentication": "headerAuth"` to parameters. |
| `SEC003` | Dangerous Code | Forbidden primitive (`eval`, `fs`, etc.) | Refactor JavaScript into safe object/array transformation. |
| `SEC004` | Leftover PinData| Non-empty `pinData` mock cache | Overwrite with empty dictionary `"pinData": {}`. |
| `LEAN001` | Unbatched Loop | Cyclic graph without `splitInBatches` | Insert `n8n-nodes-base.splitInBatches` into the cycle. |
| `LEAN002` | Missing Error | No `errorTrigger` or error workflow | Add `n8n-nodes-base.errorTrigger` node or `settings.errorWorkflow`. |
| `LLM001` | External/Bad LLM Endpoint | Missing `baseURL` or external `api.openai.com` | Set `options.baseURL: "http://localhost:8000/v1"` (or `$env` expression). |

Re-run validation after fixing until exit code is 0.

### Phase 6: Documentation & Export
Generate comprehensive markdown documentation for the workflow covering:
1. **Overview & Architecture**: Purpose, trigger mechanisms, and visual node flow.
2. **Environment Variables & Credentials**: List of required credentials and `$env` variables.
3. **Node Inventory**: Table detailing every node (`id`, `name`, `type`, purpose).
4. **Verification Status**: Output from `python scripts/n8n_validator.py <path>`.

---

## 3. Template Catalog Reference Table

All seed templates reside in `knowledge/n8n/templates/` and have been deterministically verified with 0 errors:

| Template Name | File Location | Trigger Node | Archetype / Pattern | Key Features | When to Use |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Secure Webhook** | `knowledge/n8n/templates/secure_webhook.json` | `n8n-nodes-base.webhook` (v2.0) | Authenticated Ingestion | - `headerAuth` authentication<br>- Secret token header check<br>- Dual response paths: 200 OK / 401 Unauthorized<br>- Embedded `errorTrigger` alert node | Use when receiving webhooks from third-party services (Stripe, GitHub, Shopify, custom microservices) where payload authentication and immediate HTTP status responses are required. |
| **Error Handler** | `knowledge/n8n/templates/error_handler.json` | `n8n-nodes-base.errorTrigger` (v1.0) | Incident Alerting Sub-Workflow | - Captures failed workflow execution ID<br>- Extracts error message, timestamp, and node name<br>- Formats standardized incident payload<br>- Dispatches HTTP alert to incident management / Slack webhook | Use as a dedicated, reusable sub-workflow configured via `settings.errorWorkflow` or standalone error listener across mission-critical pipelines. |
| **API Batch Polling** | `knowledge/n8n/templates/api_batch_polling.json` | `n8n-nodes-base.scheduleTrigger` (v1.2) | Resilient Batch Iteration | - Scheduled cron-like polling<br>- `splitInBatches` iteration (batch size: 50)<br>- Rate-limit throttle (`wait` node: 1s)<br>- Loop cycle back to batch controller<br>- Final aggregation / completion summary | Use when ingesting paginated REST APIs, syncing databases, or processing high-volume queues that require rate-limiting to prevent downstream 429 throttling. |
| **AI Agent Chain** | `knowledge/n8n/templates/ai_agent_chain.json` | `@n8n/n8n-nodes-langchain.chatTrigger` (v1.1) | Autonomous LangChain Agent | - `@n8n/n8n-nodes-langchain.agent` (toolsAgent v1.7)<br>- Model: `lmChatOpenAi` (`Gemini 3.7 Flash` via local `http://localhost:8000/v1`)<br>- Memory: `memoryBufferWindow`<br>- Tool: `toolHttpRequest` (API lookups)<br>- Clean sub-node port wiring | Use when building intelligent conversational assistants, multi-turn diagnostic agents, or dynamic API-orchestrating tool-calling chains. |

---

## 4. Technical Documentation Cross-References

Detailed specifications and architectural deep-dives are maintained in `knowledge/n8n/docs/`:

1. **`knowledge/n8n/docs/node_standards.md`**:
   - Canonical workflow JSON skeleton and top-level keys (`nodes`, `connections`, `settings`, `pinData`, `meta`).
   - Node schema fields: `id`, `name`, `type`, `typeVersion`, `position`, `parameters`, `credentials`.
   - Connection graph format (`main`, `ai_languageModel`, `ai_memory`, `ai_tool`).
   - Visual layout coordinate grid standards.

2. **`knowledge/n8n/docs/security_guidelines.md`**:
   - Zero plaintext secrets policy (`SEC001`) and regex pattern inventory.
   - Credential management patterns: Encrypted credentials vs `$env` expressions.
   - Webhook authentication tiers: `headerAuth`, `basicAuth`, and HMAC signature verification.
   - Sandboxing rules and code node execution restrictions (`SEC003`).
   - Mock data quarantine (`SEC004`): Ensuring `pinData` is empty in production.
   - Leanness rules: Circular connection batching (`LEAN001`) and centralized error handling (`LEAN002`).

3. **`knowledge/n8n/docs/langchain_nodes.md`**:
   - LangChain architectural model in n8n (Orchestrator vs Sub-nodes).
   - Core node types: `agent`, `lmChatOpenAi`, `memoryBufferWindow`, `toolHttpRequest`, `toolCode`.
   - Sub-node wiring conventions and connection key topologies.
   - ReAct prompting best practices and loop iteration safeguards (`maxIterations`).

---

## 5. Deterministic Validation Tooling Reference

The deterministic validator is located at `scripts/n8n_validator.py`. It requires zero external dependencies and runs under Python 3.10+.

### Command Invocations

- **Basic Validation (Single File)**:
  ```bash
  python scripts/n8n_validator.py path/to/workflow.json
  ```

- **Machine Diagnostics (JSON Output)**:
  ```bash
  python scripts/n8n_validator.py path/to/workflow.json --json
  ```

- **Strict Mode (Enforces 0 warnings; warnings become fatal exit code 1)**:
  ```bash
  python scripts/n8n_validator.py path/to/workflow.json --strict
  ```

- **Directory Validation**:
  ```bash
  python scripts/n8n_validator.py knowledge/n8n/templates/
  ```

- **Verbose Output**:
  ```bash
  python scripts/n8n_validator.py path/to/workflow.json -v
  ```

### CLI Exit Codes

| Exit Code | Status | Meaning |
| :--- | :--- | :--- |
| `0` | **PASSED** | All schema and security checks passed. Leanness warnings may exist unless `--strict` was specified. |
| `1` | **FAILED** | One or more schema (`SCH*`) or security (`SEC*`) errors detected, or warnings present under `--strict`. |
| `2` | **ERROR** | Operational failure (file does not exist, unreadable, or invalid command-line flags). |

### Machine JSON Output Schema
```json
{
  "summary": {
    "files_checked": 1,
    "passed": 0,
    "failed": 1,
    "total_errors": 1,
    "total_warnings": 0,
    "overall_valid": false
  },
  "results": [
    {
      "file": "path/to/workflow.json",
      "valid": false,
      "errors": [
        {
          "rule_id": "SEC001",
          "severity": "ERROR",
          "message": "Hardcoded OpenAI API Key pattern sk-...",
          "node": "HTTP Request",
          "location": "parameters.headerParameters[0].value"
        }
      ],
      "warnings": []
    }
  ]
}
```

---

## 6. Closed-Loop Remediation Decision Tree

When building or updating a workflow autonomously, follow this remediation loop:

```
                          [ Start / Modify Workflow ]
                                       │
                                       ▼
                       [ Run n8n_validator.py --json ]
                                       │
                         Is Exit Code == 0 & Errors == 0?
                                  /         \
                              YES /           \ NO
                                 /             \
                   [ Check Warnings ]       [ Identify Error Rule ID ]
                          │                              │
                Is --strict required?          ┌─────────┴─────────┐
                   /            \              │                   │
               YES/              \ NO        [Security]        [Schema]
                 /                \            │                   │
       Are warnings == 0?      [Proceed to   Fix:                Fix:
           /        \           Document]    - Strip secrets     - Repair JSON
       YES/          \ NO                    - Add auth          - Supply id/name
         /            \                      - Remove pinData    - Fix connections
    [Proceed]    [Fix Warnings:              - Sanitize code     - Adjust coords
                  - Add errorTrigger]          │                   │
                  - Add splitInBatches]        └─────────┬─────────┘
                          ▲                              │
                          └──────────────────────────────┘
```
