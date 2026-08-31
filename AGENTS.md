# AGENTS.md — Agent & Developer Context Guide for `hebras-ai`

Welcome to **hebras-ai**. This document provides essential architectural context, operational patterns, codebase layout, configuration options, and development guidelines for AI coding agents and human contributors working within this repository.

---

## 1. Project Overview

`hebras-ai` is an **OpenAI-compatible REST API backend** built on top of [FastAPI](https://fastapi.tiangolo.com/) that acts as an adapter layer over Google Antigravity (`agy` CLI binary).

### Key Purposes & Separation of Concerns:
- **Clean Separation of "Agents" vs "Models"**:
  - **Agents** (`GET /v1/agents`): Persona, workflow instructions, and tool configurations discovered from `.agents/agents/<name>/<name>.md` or built-in (`default`). Passed to agy via `--agent <agent>`.
  - **Models** (`GET /v1/models`): Foundational LLM engines (e.g. `Gemini 3.6 Flash (High)`, `Gemini 3.5 Pro`, `Claude 3.7 Sonnet`, `GPT-4o`). Passed to agy via `--model <model>`.
- **OpenAI-Compatible Chat Completions**: Endpoint `/v1/chat/completions` accepting `messages`, `model` (LLM model), `agent` (agent persona), `stream`, `response_format` (JSON Schema), and `interactive`.
- **Three Execution Modes**:
  1. **Non-Streaming**: Direct CLI execution with `--output-format json`.
  2. **Streaming (SSE)**: Real-time chunked streaming via `--output-format stream-json` yielding Server-Sent Events (SSE).
  3. **Interactive (PTY)**: Persistent background pseudoterminal process managed via `pexpect`, delivering prompts via carriage return (`\r`) and synchronizing responses deterministically from structured transcript logs (`transcript_full.jsonl`).
- **Session & Concurrency Management**: In-memory session tracking with turn counts, idle timeouts, background cleanup, and concurrency locks.

---

## 2. System Architecture & Request Flows

```mermaid
flowchart TD
    Client["Client / SDK / LlamaIndex / Test CLI"] -->|HTTP POST /v1/chat/completions| FastAPI["FastAPI App (backend/main.py)"]
    FastAPI --> ChatRouter["Chat Router (backend/routes/chat.py)"]
    ChatRouter --> SessionMgr["SessionManager (backend/session_manager.py)"]

    ChatRouter -->|Interactive Mode: request.interactive = true| PTYHandler["_handle_interactive()"]
    ChatRouter -->|Stream: true| StreamHandler["_handle_streaming()"]
    ChatRouter -->|Non-Streaming| SyncHandler["_handle_non_streaming()"]

    PTYHandler --> InteractiveSession["InteractiveSession (backend/agy_interactive.py)"]
    InteractiveSession -->|Spawn PTY / send \\r| AgyPTY["agy Process (PTY / pexpect)"]
    AgyPTY -->|Write structured log| Transcript["transcript_full.jsonl"]
    InteractiveSession -->|Poll for MODEL PLANNER_RESPONSE| Transcript

    StreamHandler --> StreamAgy["stream_agy() (backend/agy_process.py)"]
    StreamAgy -->|Subprocess --output-format stream-json| AgyStreamProc["agy Subprocess"]
    StreamAgy -->|SSE ChatCompletionChunk data: ...| Client

    SyncHandler --> RunAgy["run_agy() (backend/agy_process.py)"]
    RunAgy --> SafeRunner["safe_run_command() (backend/safe_runner.py)"]
    SafeRunner -->|Subprocess --output-format json| AgyProc["agy Subprocess"]
    SyncHandler -->|ChatCompletionResponse JSON| Client

    FastAPI -->|HTTP GET /v1/models| ModelsRouter["Models Router (backend/routes/models.py)"]
    ModelsRouter -->|List supported LLMs| SupportedModels["settings.agy_available_models"]

    FastAPI -->|HTTP GET /v1/agents| AgentsRouter["Agents Router (backend/routes/agents.py)"]
    AgentsRouter -->|Scan .agents/agents/*/| AgentConfigs[".agents/agents/ (.md files)"]
```

### Execution Modes Detailed

| Mode | Trigger Condition | Execution Mechanism | Response Source |
| :--- | :--- | :--- | :--- |
| **Non-Streaming** | `stream=false, interactive=false` | Executes `safe_run_command()` with `agy --print <prompt> --agent <agent> --model <model> --output-format json` | Parsed JSON stdout (`{"response": "...", "usage": ...}`) |
| **Streaming** | `stream=true, interactive=false` | Executes `stream_agy()` with `agy --agent <agent> --model <model> --output-format stream-json` | Real-time SSE chunks from `step_update.text_delta` |
| **Interactive** | `interactive=true` | Spawns long-lived `pexpect` PTY process with `TERM=dumb`, sends `\r` to submit prompt | Deterministic polling on `~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/logs/transcript_full.jsonl` |

---

## 3. Directory Structure & File Map

```
hebras-ai/
├── AGENTS.md                      # This agent context and development guide
├── README.md                      # Project documentation
├── pyproject.toml                 # Dependencies, tool configs (pytest, ruff, setuptools)
├── requirements.txt               # Requirements export
├── docker-compose.yml             # Docker deployment configuration
│
├── backend/                       # Backend Application Package
│   ├── __init__.py
│   ├── main.py                    # App factory (`create_app`), lifespan, CORS, entry point
│   ├── config.py                  # Settings (BaseSettings) reading dev.env / HEBRAS_* env vars
│   ├── types.py                   # Pydantic models for OpenAI request/response/streaming formats
│   ├── session.py                 # AgySession dataclass (turn count, timestamps, agent & model IDs)
│   ├── session_manager.py         # SessionManager pool: concurrency lock, max limit, auto-expiry
│   ├── safe_runner.py             # Process isolation, timeouts, and stdin protection (DEVNULL)
│   ├── agy_process.py             # Subprocess execution: `run_agy` (JSON) and `stream_agy` (NDJSON)
│   ├── agy_interactive.py         # InteractiveSession: persistent PTY via pexpect & transcript sync
│   ├── ansi_utils.py              # ANSI stripping and TUI chrome/spinner/banner extraction
│   ├── logging_config.py          # Structured JSON log formatter
│   └── routes/                    # API Route Definitions
│       ├── __init__.py
│       ├── chat.py                # POST /v1/chat/completions endpoint
│       ├── models.py              # GET /v1/models LLM models list & GET / root
│       └── agents.py              # GET /v1/agents dynamic agent persona discovery
│
├── integrations/                  # Framework Integrations
│   ├── __init__.py
│   └── hebras_llm.py              # LlamaIndex CustomLLM & FunctionCallingLLM implementation
│
├── scripts/                       # Developer & Test Tools
│   └── test_cli.py                # Interactive CLI tool to test chat, stream, schema, multi-turn
│
├── .agents/                       # Custom Agent Configurations
│   ├── __init__.py
│   └── agents/                    # User custom agent definitions (<name>/<name>.md)
│       └── .gitkeep
│
└── tests/                         # Pytest Suite
    ├── __init__.py
    ├── conftest.py                # Async HTTP client and SessionManager fixtures
    ├── integration/
    │   ├── __init__.py
    │   ├── test_agents_endpoint.py# Tests for /v1/agents agent persona discovery
    │   ├── test_chat_endpoint.py  # Tests for /v1/chat/completions (sync, stream, multi-turn)
    │   └── test_models_endpoint.py# Tests for /v1/models LLM models list
    └── unit/
        ├── __init__.py
        ├── test_agy_interactive.py# Unit tests for InteractiveSession & transcript sync
        ├── test_agy_process.py    # Unit tests for run_agy and stream_agy
        ├── test_ansi_utils.py     # Unit tests for ANSI stripping & chrome extraction
        ├── test_llama_index_extended.py
        ├── test_llama_index_integration.py
        ├── test_safe_runner.py    # Unit tests for safe_run_command & timeout enforcement
        ├── test_session.py        # Unit tests for AgySession lifecycle
        ├── test_session_manager.py# Unit tests for SessionManager pool & eviction
        ├── test_session_manager_concurrency.py # Concurrent session creation/deletion tests
        └── test_types.py          # Unit tests for Pydantic type conversions & aliases
```

---

## 4. Agents vs Models Specification

### Agent Discovery (`GET /v1/agents`)
Agents are defined as Markdown files within `.agents/agents/<agent_name>/<agent_name>.md`.
```markdown
---
name: code_reviewer
description: Expert code reviewer
tools:
  - read_file(*)
commandExecutionPolicy: off
---
System instructions...
```
`GET /v1/agents` returns a list of `AgentInfo` objects containing `id`, `name`, `description`, `tools`, and `command_execution_policy`.

### Model Listing (`GET /v1/models`)
`GET /v1/models` returns a list of `ModelInfo` objects for available foundational LLMs (e.g. `Gemini 3.6 Flash (High)`, `Gemini 3.5 Pro`, `Claude 3.7 Sonnet`, `GPT-4o`).

---

## 5. Configuration & Environment Variables

Settings are managed in `backend/config.py` using `pydantic-settings`. They can be loaded from `dev.env` or from environment variables prefixed with `HEBRAS_`.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `HEBRAS_HOST` | `str` | `"127.0.0.1"` | Host to bind the API server |
| `HEBRAS_PORT` | `int` | `8000` | Port to bind the API server |
| `HEBRAS_AGY_BINARY` | `str` | `"agy"` | Path or name of the agy CLI binary |
| `HEBRAS_AGY_DEFAULT_AGENT` | `str` | `"default"` | Default agent persona if unspecified |
| `HEBRAS_AGY_DEFAULT_MODEL` | `str` | `"Gemini 3.6 Flash (High)"` | Default underlying foundational LLM model |
| `HEBRAS_AGY_DEFAULT_TIMEOUT` | `int` | `120` | Execution timeout (seconds) for non-streaming commands |
| `HEBRAS_AGY_DEFAULT_WORKSPACE` | `str` | `"."` | Default workspace directory passed via `--add-dir` |
| `HEBRAS_AGY_AGENTS_DIR` | `str` | `".agents/agents"` | Directory scanned for custom agent configs |
| `HEBRAS_AGY_DEFAULT_MODE` | `str \| None` | `None` | Default agy mode (`plan`, `accept-edits`, etc.) |
| `HEBRAS_AGY_DANGEROUSLY_SKIP_PERMISSIONS` | `bool` | `False` | Auto-approve tool execution in agy |
| `HEBRAS_AGY_INTERACTIVE_TIMEOUT` | `int` | `180` | Interactive session response timeout (seconds) |
| `HEBRAS_AGY_LOG_DIR` | `str` | `"log"` | Directory where PTY dump and session logs are written |
| `HEBRAS_MAX_SESSIONS` | `int` | `10` | Maximum active concurrent sessions in the pool |
| `HEBRAS_SESSION_IDLE_TIMEOUT` | `int` | `600` | Session idle expiration threshold (seconds) |
| `HEBRAS_LOG_LEVEL` | `str` | `"INFO"` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HEBRAS_LOG_FORMAT` | `str` | `"json"` | Log format (`"json"` or `"text"`) |

---

## 6. Development Workflows & Commands

### 1. Environment Setup
The project uses Python 3.12+ and `uv` / standard virtual environments:
```bash
source .venv/bin/activate
```

### 2. Running the API Server
```bash
# Using uvicorn with hot reload
uvicorn backend.main:app --reload --port 8000

# Or using the backend entry point directly
python -m backend.main
```

### 3. Running Automated Tests
```bash
# Run entire test suite
pytest -v
```

### 4. Interactive Test CLI
```bash
python scripts/test_cli.py
```

Commands available in `test_cli.py`:
- `agents`: List discovered agent personas (`GET /v1/agents`).
- `agent <name>`: Switch active agent persona.
- `models`: List available foundational LLM models (`GET /v1/models`).
- `model <name>`: Switch active LLM model.
- `chat <prompt>`: Send non-streaming chat completion.
- `stream <prompt>`: Send streaming chat completion via SSE.
- `schema <prompt>`: Send completion with JSON Schema enforcement.
- `multi`: Start an interactive multi-turn conversation.
