# n8n Node Standards & Schema Specification

This document provides the foundational engineering standard for constructing valid, lean, and deterministic n8n workflows within the `hebras-ai` ecosystem. Workflows adhering to this standard will pass all schema rules (`SCH001`-`SCH006`) enforced by `scripts/n8n_validator.py`.

---

## 1. Top-Level Workflow Structure

An n8n workflow file is a UTF-8 encoded JSON object consisting of at least two mandatory top-level keys: `nodes` and `connections`. Additional runtime metadata keys (`settings`, `pinData`, `meta`) should be explicitly defined.

### Canonical Workflow Skeleton
```json
{
  "name": "Production Workflow Name",
  "nodes": [],
  "connections": {},
  "settings": {
    "executionOrder": "v1"
  },
  "pinData": {},
  "meta": {
    "templateCredsSetupCompleted": true
  }
}
```

| Key | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Optional | Human-readable workflow title. |
| `nodes` | `Array<Node>` | **Mandatory** (`SCH002`) | Array of node configuration objects in the workflow. |
| `connections` | `Object` | **Mandatory** (`SCH002`) | Adjacency dictionary mapping node outputs to node inputs. |
| `settings` | `Object` | Recommended | Workflow execution options (e.g. `executionOrder`, `errorWorkflow`). |
| `pinData` | `Object` | **Mandatory** (`SEC004`) | Mock execution cache. **Must be empty (`{}`) in production**. |
| `meta` | `Object` | Optional | UI rendering flags and workflow instance metadata. |

---

## 2. Node Object Specification

Every object within the `nodes` array must satisfy the schema requirements validated by `SCH003`, `SCH004`, and `SCH005`.

### Node Schema Fields
```json
{
  "id": "c1a60395-e1d2-4ee1-b0db-9f22572183e8",
  "name": "Fetch Active Users",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [460, 300],
  "parameters": {
    "method": "GET",
    "url": "={{ $env.USER_SERVICE_URL }}/api/v1/users"
  },
  "credentials": {}
}
```

### Field Definitions & Constraints

| Field | Type | Rule Code | Constraint & Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | `SCH003` | Non-empty UUID string (e.g. `uuid4()`). Used by n8n UI and execution telemetry. |
| `name` | `string` | `SCH003`, `SCH004` | **Globally unique** non-empty string. Acts as the primary foreign key for `connections`. |
| `type` | `string` | `SCH003` | Fully qualified package and node identifier (e.g. `n8n-nodes-base.webhook` or `@n8n/n8n-nodes-langchain.agent`). |
| `typeVersion` | `number` | `SCH003` | Numeric version (e.g. `1`, `2`, `4.2`). Pins the parameter schema. Boolean or null values are prohibited. |
| `position` | `[number, number]` | `SCH005` | Exactly 2 numeric canvas coordinates `[x, y]`. |
| `parameters` | `object` | `SCH003` | Key-value dictionary containing node-specific configuration. Must be a valid dictionary, never null. |
| `credentials` | `object` | `SEC001` | Optional dictionary mapping credential types to credential references (e.g. `{"openAiApi": {"id": "1", "name": "OpenAI"}}`). |
| `disabled` | `boolean` | Optional | When `true`, execution bypasses this node. |
| `notesInFlow` | `boolean` | Optional | When `true`, displays sticky note in UI canvas. |

---

## 3. Node Naming Conventions

The `name` property is the structural anchor of the entire workflow DAG.

1. **Uniqueness Requirement (`SCH004`)**:
   - Duplicate names are illegal and break graph execution.
   - **Incorrect**: Having two nodes named `"HTTP Request"`.
   - **Correct**: `"HTTP Request - Get Customer"`, `"HTTP Request - Update CRM"`.
2. **Action-Oriented Syntax**:
   - Follow `[Verb] + [Target/Context]` format.
   - Examples: `Verify Signature`, `Extract Token`, `Filter Active Subscribers`, `Send Slack Alert`.
3. **Character Safety**:
   - Allowed characters: Letters, numbers, spaces, hyphens, parentheses.
   - Avoid symbols that collide with n8n's expression engine syntax: `$`, `{{`, `}}`, `"`, `'`, `.`.
   - Reference pattern: In expressions, nodes are accessed via `$('Node Name').item.json.property`.

---

## 4. Connections Architecture & DAG Topology

n8n organizes connections as a 3-level nested dictionary:
`connections` -> `sourceNodeName` -> `connectionType` -> `outputIndex` -> `targetArray`.

### Connection Topology Structure
```json
"connections": {
  "Webhook Trigger": {
    "main": [
      [
        {
          "node": "Verify Payload",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "Verify Payload": {
    "main": [
      [
        {
          "node": "Process Payment",
          "type": "main",
          "index": 0
        }
      ],
      [
        {
          "node": "Reject Request",
          "type": "main",
          "index": 0
        }
      ]
    ]
  }
}
```

### Connection Types

1. **`main` Connections (Data Pipeline)**:
   - Primary flow of JSON data items.
   - `outputIndex 0`: Standard output for linear nodes, or the `true` / `loop` output for branching nodes (`If`, `SplitInBatches`).
   - `outputIndex 1`: The `false` branch for `If` nodes, or the `done` branch for `SplitInBatches`.
2. **AI Sub-Node Connections (`@n8n/n8n-nodes-langchain`)**:
   - Connects functional components into an Agent or Chain.
   - **Directionality Convention**: In n8n JSON, the connection is authored **from the sub-node pointing into the consumer agent node**.
   - Connection types:
     - `ai_languageModel`: Connects Chat Models (`lmChatOpenAi`, etc.) to Agent.
     - `ai_memory`: Connects Memory nodes (`memoryBufferWindow`, etc.) to Agent.
     - `ai_tool`: Connects Tool nodes (`toolHttpRequest`, `toolWorkflow`, etc.) to Agent.
     - `ai_outputParser`: Connects Output Parsers to Chain.
     - `ai_embedding`: Connects Embeddings to Vector Stores.

### Connection Integrity Invariant (`SCH006`)
- Every key in `connections` must exist in `nodes`.
- Every `node` target in each branch array must exist in `nodes`.
- Dangling connection references will fail validation with `SCH006_DANGLING_CONNECTION`.

---

## 5. Canvas Coordinate Grid & Layout Standards

Consistent canvas coordinates ensure workflows are immediately legible and maintainable when viewed in the visual canvas.

### Standard Grid Spacing
- **X-axis (Time & Pipeline Progress)**:
  - Base spacing ($\Delta x$): **$220\text{px}$** between sequential nodes.
  - Recommended sequence: $240 \to 460 \to 680 \to 900 \to 1120 \to 1340$.
- **Y-axis (Branches & Hierarchy)**:
  - Main pipeline centerline: $y = 300$.
  - True / Primary Branch: $y = 200$ (upwards by $100\text{px}$).
  - False / Fallback Branch: $y = 400$ (downwards by $100\text{px}$).
  - AI Sub-Nodes (Model, Memory, Tools): Docked beneath the parent Agent node at $y = 520$ ($\Delta y = +220\text{px}$), horizontally staggered by $\Delta x = 180\text{px}$.
  - Error Trigger nodes: Positioned above the pipeline at $y = 100$ or below at $y = 540$, completely detached from the `main` connection DAG.

### Layout Matrix Example
```
[y=100]  [Error Trigger] (isolated)
             |
[y=200]                             [Success Response]
                                       ^ (branch 0)
[y=300]  [Webhook] -> [Verify Hash] -> [If Valid?]
                                       v (branch 1)
[y=400]                             [Error 401 Response]
```

---

## 6. Local LLM Wrapper Standard (`LLM001`)

To maintain complete security isolation, predictable reflection control, and avoid external API dependencies, **all LLM reasoning in n8n workflows must target the local Antigravity API wrapper** (`http://localhost:8000/v1/...`).

### 6.1 LangChain Chat Model Nodes (`lmChatOpenAi`)
- **Mandatory Option**: Must include `"baseURL": "http://localhost:8000/v1"` (or an expression like `={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}`).
- **Model Selection**: Clean model identifiers discovered from `GET /v1/models` (`"Gemini 3.7 Flash"`, `"Gemini 3.6 Flash"`, `"Claude Sonnet 4.6"`, `"GPT-OSS 120B"`).
- **Credentials**: Uses an `openAiApi` credential object referencing the local wrapper (e.g. `hebras_agy_local`).

```json
{
  "name": "Hebras Agy Chat Model",
  "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
  "typeVersion": 1.2,
  "parameters": {
    "model": "Gemini 3.7 Flash",
    "options": {
      "baseURL": "http://localhost:8000/v1",
      "temperature": 0.2
    }
  },
  "credentials": {
    "openAiApi": {
      "id": "hebras_agy_local",
      "name": "Hebras Agy Local API"
    }
  }
}
```

### 6.2 Direct HTTP Request Nodes for LLM Completion
For simple workflows calling chat completions without LangChain agent scaffolding, configure `n8n-nodes-base.httpRequest`:
- **URL**: `"http://localhost:8000/v1/chat/completions"` (or `={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}/chat/completions`)
- **Method**: `POST`
- **Body Parameters**:
  ```json
  {
    "model": "Gemini 3.7 Flash",
    "messages": [
      {
        "role": "user",
        "content": "={{ $json.prompt }}"
      }
    ]
  }
  ```
- Any chat completions HTTP Request calling external endpoints like `https://api.openai.com/v1/chat/completions` will fail validation under `LLM001`.

