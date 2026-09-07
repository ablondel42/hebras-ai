# n8n LangChain AI Ecosystem Specification

This document provides the reference guide for constructing advanced AI agent workflows using `@n8n/n8n-nodes-langchain` nodes. It details node specifications, sub-node connection wiring, credential handling, and memory orchestration.

---

## 1. Architectural Model

n8n implements LangChain as a modular tree of specialized nodes connected to an orchestrator node:
- **Orchestrator Node**: `@n8n/n8n-nodes-langchain.agent` or `@n8n/n8n-nodes-langchain.chainLlm`.
- **Sub-Nodes (Providers)**: Model, Memory, Tools, Embeddings, Output Parsers, Vector Stores.

```
       [Chat Trigger]
             | (main)
             v
       [ AI Agent ] <====== (ai_languageModel) ====== [ Hebras Agy Chat Model ]
          ||    ||                                      (http://localhost:8000/v1)
          ||    `=========== (ai_memory) ============= [ Window Buffer Memory ]
          `================= (ai_tool) =============== [ HTTP Request Tool ]
```

---

## 2. Core Node Specifications

### 2.1 AI Agent Node (`@n8n/n8n-nodes-langchain.agent`)
The central reasoning engine executing ReAct (Reason + Act) tool-calling loops.

- **Type**: `@n8n/n8n-nodes-langchain.agent`
- **Current Version**: `1.7`
- **Key Parameters**:
  - `agent`: Agent archetype:
    - `"toolsAgent"` (Default, recommended): Uses model function/tool calling.
    - `"conversationalAgent"`: Standard conversational ReAct agent.
    - `"planAndExecuteAgent"`: Multi-step planner.
  - `promptType`: `"define"` (explicit expression prompt) or `"auto"` (reads from trigger).
  - `text`: Input query expression, e.g. `={{ $json.chatInput }}`.
  - `options`:
    - `systemMessage`: System prompt defining agent persona, constraints, and instructions.
    - `maxIterations`: Safeguard cap against infinite tool execution (e.g. `10`).
    - `returnIntermediateSteps`: Boolean flag to inspect tool calling reasoning.

### 2.2 Chat Language Model Nodes (`lmChatOpenAi` / Local Agy Wrapper)
Provides LLM capabilities to the Agent node via the local OpenAI-compatible `hebras-ai` API wrapper (`http://localhost:8000/v1`).

> [!IMPORTANT]
> **Local Endpoint Invariant (`LLM001`)**: All LLM model nodes must set `options.baseURL` to `http://localhost:8000/v1` (or expression `={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}`). Never route traffic to external public endpoints like `api.openai.com`.

- **Type**: `@n8n/n8n-nodes-langchain.lmChatOpenAi`
- **Current Version**: `1.2`
- **Connection Port**: `ai_languageModel`
- **Key Parameters**:
  - `model`: Clean foundational model discovered dynamically via `GET /v1/models`:
    - `"Gemini 3.8 Flash"` (Recommended default)
    - `"Gemini 3.7 Flash"`
    - `"Gemini 3.6 Flash"`
    - `"Claude Sonnet 4.6"`
    - `"GPT-OSS 120B"`
  - `options`:
    - `baseURL`: Mandatory local endpoint: `"http://localhost:8000/v1"` (or `={{ $env.HEBRAS_API_BASE_URL || 'http://localhost:8000/v1' }}`).
    - `temperature`: Creativity slider (`0.0` to `1.0`, recommended `0.2` for deterministic tools).
    - `maxTokens`: Token generation budget (e.g. `2048`).
- **Credentials**:
  - Uses an encrypted credential ID (`openAiApi`) pointing to the local service (dummy local key acceptable since authentication is governed locally):
    ```json
    "credentials": {
      "openAiApi": {
        "id": "hebras_agy_local",
        "name": "Hebras Agy Local API"
      }
    }
    ```

### 2.3 Window Buffer Memory Node (`memoryBufferWindow`)
Maintains conversational context across multi-turn interactions.

- **Type**: `@n8n/n8n-nodes-langchain.memoryBufferWindow`
- **Current Version**: `1.3`
- **Connection Port**: `ai_memory`
- **Key Parameters**:
  - `contextWindowLength`: Number of previous interaction turns stored in context (e.g. `10`).
  - `sessionKey`: Unique session identifier expression (e.g. `={{ $json.sessionId || $json.chatSessionId }}`).

### 2.4 Tool Nodes (`toolHttpRequest`, `toolWorkflow`)
Exposes external capabilities and sub-workflows for the LLM to invoke autonomously.

#### Tool 1: HTTP Request Tool (`toolHttpRequest`)
- **Type**: `@n8n/n8n-nodes-langchain.toolHttpRequest`
- **Current Version**: `1.1`
- **Connection Port**: `ai_tool`
- **Key Parameters**:
  - `name`: Machine-readable tool name (letters and underscores only, e.g. `"query_knowledge_base"`).
  - `description`: Detailed description explaining when and how the LLM should invoke this tool.
  - `method`: HTTP method (`GET`, `POST`, etc.).
  - `url`: Endpoint URL, e.g. `={{ $env.SEARCH_SERVICE_URL }}/api/search`.

#### Tool 2: Workflow Tool (`toolWorkflow`)
- **Type**: `@n8n/n8n-nodes-langchain.toolWorkflow`
- **Current Version**: `1.1`
- **Connection Port**: `ai_tool`
- **Key Parameters**:
  - `name`: Machine-readable tool name (e.g. `"execute_database_lookup"`).
  - `description`: Explains business logic performed by the sub-workflow.
  - `workflowId`: n8n ID of the workflow to invoke.

---

## 3. Sub-Node Wiring Architecture

In n8n JSON exports, connections between sub-nodes and the agent are expressed **from the sub-node towards the agent**, using the corresponding sub-node connection type.

### Connection Block Definition
```json
"connections": {
  "Chat Trigger": {
    "main": [
      [
        {
          "node": "AI Agent",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "OpenAI Chat Model": {
    "ai_languageModel": [
      [
        {
          "node": "AI Agent",
          "type": "ai_languageModel",
          "index": 0
        }
      ]
    ]
  },
  "Window Buffer Memory": {
    "ai_memory": [
      [
        {
          "node": "AI Agent",
          "type": "ai_memory",
          "index": 0
        }
      ]
    ]
  },
  "HTTP Search Tool": {
    "ai_tool": [
      [
        {
          "node": "AI Agent",
          "type": "ai_tool",
          "index": 0
        }
      ]
    ]
  }
}
```

---

## 4. Complete Canonical AI Agent Workflow Example

```json
{
  "name": "Canonical AI Agent Chain",
  "nodes": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "Error Trigger",
      "type": "n8n-nodes-base.errorTrigger",
      "typeVersion": 1,
      "position": [240, 100],
      "parameters": {}
    },
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "name": "Chat Trigger",
      "type": "@n8n/n8n-nodes-langchain.chatTrigger",
      "typeVersion": 1.1,
      "position": [240, 300],
      "parameters": {}
    },
    {
      "id": "33333333-3333-3333-3333-333333333333",
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 1.7,
      "position": [480, 300],
      "parameters": {
        "agent": "toolsAgent",
        "promptType": "define",
        "text": "={{ $json.chatInput }}",
        "options": {
          "systemMessage": "You are a secure, helpful enterprise assistant."
        }
      }
    },
    {
      "id": "44444444-4444-4444-4444-444444444444",
      "name": "Hebras Agy Chat Model",
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "typeVersion": 1.2,
      "position": [360, 520],
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
    },
    {
      "id": "55555555-5555-5555-5555-555555555555",
      "name": "Window Buffer Memory",
      "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
      "typeVersion": 1.3,
      "position": [540, 520],
      "parameters": {
        "contextWindowLength": 10,
        "sessionKey": "={{ $json.sessionId }}"
      }
    },
    {
      "id": "66666666-6666-6666-6666-666666666666",
      "name": "HTTP Search Tool",
      "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
      "typeVersion": 1.1,
      "position": [720, 520],
      "parameters": {
        "name": "api_search",
        "description": "Searches external documentation and API resources",
        "url": "={{ $env.SEARCH_SERVICE_URL }}/search",
        "method": "GET"
      }
    }
  ],
  "connections": {
    "Chat Trigger": {
      "main": [
        [
          {
            "node": "AI Agent",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Hebras Agy Chat Model": {
      "ai_languageModel": [
        [
          {
            "node": "AI Agent",
            "type": "ai_languageModel",
            "index": 0
          }
        ]
      ]
    },
    "Window Buffer Memory": {
      "ai_memory": [
        [
          {
            "node": "AI Agent",
            "type": "ai_memory",
            "index": 0
          }
        ]
      ]
    },
    "HTTP Search Tool": {
      "ai_tool": [
        [
          {
            "node": "AI Agent",
            "type": "ai_tool",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  },
  "pinData": {}
}
```

---

## 5. Engineering Pitfalls & Best Practices

1. **Deterministic Tool Descriptions**:
   - The LLM selects tools based purely on the `description` parameter. Make descriptions specific, operational, and explicit about inputs and outputs.
2. **Session Key Isolation**:
   - Always supply an explicit expression in `sessionKey` for memory nodes. Omitting `sessionKey` causes state pollution across different users.
3. **Hardcoded Credentials Avoidance**:
   - In tool nodes making external calls, never hardcode authentication headers. Use n8n credentials or `={{ $env.TOKEN }}` expressions.
4. **Error Handling**:
   - Always pair an AI Agent workflow with an `errorTrigger` node (`LEAN002`) to intercept external LLM timeouts and tool API errors.
