# n8n Production Security & Sandboxing Guidelines

This guide defines the production security standards and zero-trust engineering principles for n8n workflows in `hebras-ai`. Adhering to these rules guarantees workflows pass all security validation gates (`SEC001`-`SEC004`) and leanness checks (`LEAN001`-`LEAN002`) enforced by `scripts/n8n_validator.py`.

---

## 1. Zero Plaintext Secrets Policy (`SEC001`)

**Rule `SEC001`**: Workflow JSON files must **never** contain raw, unencrypted secrets, API tokens, passwords, private keys, or credentials.

### Prohibited Secret Patterns
The validator CLI actively scans for the following token signatures:
- **OpenAI Keys**: `sk-[a-zA-Z0-9_-]{15,}`
- **Anthropic Keys**: `sk-ant-[a-zA-Z0-9_-]{15,}`
- **GitHub PATs**: `ghp_`, `gho_`, `github_pat_`
- **Slack Tokens**: `xoxb-`, `xoxa-`, `xoxp-`
- **AWS Access Keys**: `AKIA[0-9A-Z]{16}`, `ASIA[0-9A-Z]{16}`
- **Google API Keys**: `AIzaSy[0-9A-Za-z_-]{20,}`
- **Bearer Tokens**: `Bearer <token>` literals
- **Private Keys**: `-----BEGIN PRIVATE KEY-----` or `-----BEGIN RSA PRIVATE KEY-----`
- **Sensitive Parameters**: Literal values assigned to fields containing `password`, `secret`, `api_key`, `token`, `auth`.

### Allowed Credential Management Patterns

#### Pattern A: Safe Credential Reference (Recommended for Platform UI)
Nodes reference credential objects stored in n8n's encrypted database:
```json
{
  "credentials": {
    "openAiApi": {
      "id": "1",
      "name": "Production OpenAI Account"
    }
  }
}
```

#### Pattern B: Environment Variable Expressions (Recommended for CI/CD & GitOps)
Dynamic expressions evaluated at runtime by n8n's expression engine:
```json
{
  "parameters": {
    "url": "https://api.service.com/v1/data",
    "headerParameters": {
      "parameters": [
        {
          "name": "Authorization",
          "value": "={{ 'Bearer ' + $env.EXTERNAL_SERVICE_API_KEY }}"
        }
      ]
    }
  }
}
```

#### Pattern C: External Secrets Vault Expressions
Workflows deployed with n8n Enterprise external secret integrations:
```json
{
  "parameters": {
    "apiKey": "={{ $secrets.STRIPE_SECRET_KEY }}"
  }
}
```

---

## 2. Webhook Authentication Tiers (`SEC002`)

**Rule `SEC002`**: Any `n8n-nodes-base.webhook` node configured without authentication (`authentication: "none"` or missing `authentication`) is a critical security vulnerability and will trigger a hard failure.

### Supported Authentication Modes

| Mode | Parameter Value | Mechanism | Use Case |
| :--- | :--- | :--- | :--- |
| **Header Auth** | `"headerAuth"` | Verifies incoming static header value against n8n credentials. | Service-to-service internal webhooks, API gateways. |
| **Basic Auth** | `"basicAuth"` | RFC 7617 username and password HTTP challenge. | Legacy system integration, webhook alerts. |
| **JWT Auth** | `"jwtAuth"` | Validates signed JSON Web Token (RS256 / HS256). | Front-end apps, OAuth2 identity providers. |

### Configuration Example
```json
{
  "name": "Incoming Webhook",
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 2,
  "position": [240, 300],
  "parameters": {
    "httpMethod": "POST",
    "path": "events-listener",
    "authentication": "headerAuth",
    "responseMode": "responseNode"
  }
}
```

### Defense-in-Depth: HMAC Cryptographic Verification
For third-party webhooks (e.g. GitHub, Stripe, Shopify), header authentication should be augmented with cryptographic HMAC signature verification inside a downstream Code node:

```javascript
// Safe JavaScript Code Node: Verify HMAC Signature
const crypto = require('crypto'); // Note: if crypto is pre-whitelisted or use pure JS hash
const signature = $input.item.json.headers['x-hub-signature-256'];
const secret = $env.WEBHOOK_HMAC_SECRET;
const payload = JSON.stringify($input.item.json.body);

const expectedSignature = 'sha256=' + crypto.createHmac('sha256', secret).update(payload).digest('hex');

if (signature !== expectedSignature) {
  return [{ json: { authorized: false, error: 'Invalid HMAC signature' } }];
}

return [{ json: { authorized: true, data: $input.item.json.body } }];
```

---

## 3. Safe Code Node Sandboxing (`SEC003`)

**Rule `SEC003`**: Code nodes (`n8n-nodes-base.code`, `function`, `functionItem`) run within restricted execution contexts. Any attempt to execute forbidden system primitives or escape the sandbox will trigger a hard validation error.

### Forbidden Constructs (Instant Hard Error)

#### JavaScript Violations:
- `eval(...)`
- `Function(...)` constructor
- `child_process` (`exec`, `spawn`, `fork`)
- `require('fs')` or `require('node:fs')`
- Network socket access: `require('net')`, `require('tls')`, `require('dgram')`, `require('cluster')`
- Process termination: `process.exit()`, `process.kill()`, `process.abort()`

#### Python Violations:
- `eval(...)`, `exec(...)`, `compile(...)`
- `import os` or `os.system`, `os.popen`, `os.remove`
- `import subprocess`
- `import sys` or `sys.exit`
- `__import__(...)`, `importlib`
- File operations: `open(...)`

### Safe Code Node Standard Pattern
Code nodes should perform deterministic, side-effect-free data transformations using n8n's data API (`$input`):

```javascript
// Safe JS Code Node Example
const items = $input.all();

return items.map(item => {
  const rawData = item.json;
  return {
    json: {
      userId: rawData.id,
      fullName: `${rawData.first_name} ${rawData.last_name}`.trim(),
      isActive: Boolean(rawData.status === 'active'),
      processedAt: new Date().toISOString()
    }
  };
});
```

---

## 4. Stripping Leftover `pinData` (`SEC004`)

**Rule `SEC004`**: The n8n canvas editor saves temporary test execution data inside the top-level `"pinData"` key. This mock data frequently contains live PII, database rows, customer names, or temporary tokens.

- **Requirement**: Before exporting or committing a workflow JSON, `pinData` must be emptied:
  ```json
  "pinData": {}
  ```
- **Linter Behavior**: Workflows with non-empty `pinData` will fail validation with `SEC004_LEFTOVER_PINDATA`.

---

## 5. Leanness & Reliability Rules

### Batched Loop Control (`LEAN001`)
- Workflows that contain circular `main` connection cycles must include a batching node: `n8n-nodes-base.splitInBatches` or `n8n-nodes-base.loopOverItems`.
- Unbatched loops cause runaway execution, memory exhaustion, and infinite API loops.
- Emits warning `LEAN001_UNBATCHED_LOOP`.

### Error Handling Requirement (`LEAN002`)
- Workflows must never fail silently in production.
- Every workflow must provide either:
  1. An `n8n-nodes-base.errorTrigger` node inside the workflow itself, OR
  2. A reference to an error workflow in `settings.errorWorkflow`:
- Emits warning `LEAN002_MISSING_ERROR_TRIGGER` if neither is found.

---

## 6. Local Model Governance & Data Sovereignty (`LLM001`)

**Rule `LLM001`**: All LLM interactions (LangChain chat model nodes and HTTP Request completion nodes) must route strictly through the local `hebras-ai` Antigravity API wrapper (`http://localhost:8000/v1/...`).

### Security Rationale
1. **Zero External Data Exfiltration**: Prompt payloads, user data, and system messages remain strictly within the local host/sandbox boundary.
2. **Elimination of Third-Party API Key Exposure**: Eliminates the need to store third-party OpenAI/Anthropic API keys inside n8n workflow JSON files or environment variables.
3. **Local Process Isolation**: Antigravity runs as a protected local process (`agy` CLI) governed by `hebras-ai` safe execution wrappers with stdin protections and idle timeouts.
4. **Hard Enforcement**: `scripts/n8n_validator.py` strictly fails any workflow using `@n8n/n8n-nodes-langchain.lmChatOpenAi` lacking `options.baseURL` pointing to localhost or referencing `$env.HEBRAS_API_BASE_URL`.

