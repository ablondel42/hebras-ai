# AGENTS.md — Agent & Developer Context Guide for `hebras-ai`

Welcome to **hebras-ai**. This document provides essential architectural context, operational patterns, codebase layout, configuration options, and development guidelines for AI coding agents and human contributors working within this repository.

---

## 1. Project Overview

`hebras-ai` is an **OpenAI-compatible REST API backend** built on top of [FastAPI](https://fastapi.tiangolo.com/) that acts as an adapter layer over Google Antigravity (`agy` CLI binary).

### Key Purposes & Separation of Concerns:
- **Clean Separation of "Agents" vs "Models"**:
  - **Agents** (`GET /v1/agents`): Persona, workflow instructions, and tool configurations discovered from `.agents/agents/<name>/<name>.md` or built-in (`default`). Passed to agy via `--agent <agent>`.
  - **Models** (`GET /v1/models`): Foundational LLM engines discovered dynamically via `agy models` (e.g. `Gemini 3.7 Flash`, `Gemini 3.6 Flash`, `Gemini 3.1 Pro`, `Claude Sonnet 4.6`, `Claude Opus 4.6`, `GPT-OSS 120B`) with reflection level parentheticals cleaned up.
- **Reflection / Reasoning Effort Control**:
  - `POST /v1/chat/completions` accepts `model` and `reflection` (or `reasoning_effort`: `low`, `medium`, `high`), dynamically mapping to the corresponding `agy` target (default: `Gemini 3.7 Flash (High)`).
- **OpenAI-Compatible Chat Completions**: Endpoint `/v1/chat/completions` accepting `messages`, `model` (LLM model), `agent` (agent persona), `reflection` / `reasoning_effort`, `stream`, `response_format` (JSON Schema), and `interactive`.
- **Execution Modes**:
  1. **Non-Streaming**: Direct CLI execution with `--output-format json`.
  2. **Streaming (SSE)**: Real-time chunked streaming via `--output-format stream-json` yielding Server-Sent Events (SSE), supporting both single-turn and multi-turn conversations with `--conversation <id>`.
  3. **Interactive (PTY)**: Persistent background pseudoterminal process managed via `pexpect`, delivering prompts via carriage return (`\r`) and synchronizing responses deterministically from structured transcript logs (`transcript_full.jsonl`).
- **Session & Concurrency Management**: In-memory session tracking with turn counts, idle timeouts, background cleanup, and concurrency locks.
- **Evaluation & Deep Inspection Logging**:
  - `log/<conversation_id>.log`: Complete turn logs containing full prompts, thinking/reflection, responses, duration, and token usage breakdowns.
  - `log/hebras.log`: Server log with local timezone offsets (`+02:00`). When `HEBRAS_LOG_LEVEL=DEV`, records the complete user-model message exchange including LLM reflection/thinking.

---

## 2. System Architecture & Request Flows

```mermaid
flowchart TD
    Client["Client / SDK / LlamaIndex / Test CLI"] -->|HTTP POST /v1/chat/completions| FastAPI["FastAPI App (backend/main.py)"]
    FastAPI --> ChatRouter["Chat Router (backend/routes/chat.py)"]
    ChatRouter --> SessionMgr["SessionManager (backend/session_manager.py)"]

    ChatRouter -->|Interactive Mode: request.interactive = true| PTYHandler["_handle_interactive()"]
    ChatRouter -->|Stream: true (Single or Multi-Turn)| StreamHandler["_handle_streaming()"]
    ChatRouter -->|Non-Streaming| SyncHandler["_handle_non_streaming()"]

    PTYHandler --> InteractiveSession["InteractiveSession (backend/agy_interactive.py)"]
    InteractiveSession -->|Spawn PTY / send \\r| AgyPTY["agy Process (PTY / pexpect)"]
    AgyPTY -->|Write structured log| Transcript["transcript_full.jsonl"]
    InteractiveSession -->|Poll for MODEL PLANNER_RESPONSE| Transcript

    StreamHandler --> StreamAgy["stream_agy() (backend/agy_process.py)"]
    StreamAgy -->|Subprocess --output-format stream-json [--conversation <id>]| AgyStreamProc["agy Subprocess"]
    StreamAgy -->|SSE ChatCompletionChunk data: ...| Client

    SyncHandler --> RunAgy["run_agy() (backend/agy_process.py)"]
    RunAgy --> SafeRunner["safe_run_command() (backend/safe_runner.py)"]
    SafeRunner -->|Subprocess --output-format json [--conversation <id>]| AgyProc["agy Subprocess"]
    SyncHandler -->|ChatCompletionResponse JSON| Client

    FastAPI -->|HTTP GET /v1/models| ModelsRouter["Models Router (backend/routes/models.py)"]
    ModelsRouter -->|Dynamic Discovery| AgyModelsCLI["safe_run_command(['agy', 'models'])"]

    FastAPI -->|HTTP GET /v1/agents| AgentsRouter["Agents Router (backend/routes/agents.py)"]
    AgentsRouter -->|Scan .agents/agents/*/| AgentConfigs[".agents/agents/ (.md files)"]
```

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
│   ├── config.py                  # Settings (BaseSettings) reading .env / dev.env / HEBRAS_* env vars
│   ├── types.py                   # Pydantic models for OpenAI request/response/streaming formats
│   ├── session.py                 # AgySession dataclass (turn count, timestamps, agent & model IDs)
│   ├── session_manager.py         # SessionManager pool: concurrency lock, max limit, auto-expiry
│   ├── safe_runner.py             # Process isolation, timeouts, and stdin protection (DEVNULL)
│   ├── agy_process.py             # Subprocess execution: `run_agy` (JSON) and `stream_agy` (NDJSON)
│   ├── agy_interactive.py         # InteractiveSession: persistent PTY via pexpect & transcript sync
│   ├── ansi_utils.py              # ANSI stripping and TUI chrome/spinner/banner extraction
│   ├── logging_config.py          # Structured JSON log formatter (DEV level, local timezone)
│   ├── turn_logger.py             # Human-readable evaluation and turn logger (`log/<id>.log`, reflection extraction)
│   └── routes/                    # API Route Definitions
│       ├── __init__.py
│       ├── chat.py                # POST /v1/chat/completions endpoint (streaming, non-streaming, PTY, DEV log)
│       ├── models.py              # GET /v1/models dynamic model discovery & reflection resolver
│       └── agents.py              # GET /v1/agents dynamic agent persona discovery
│
├── integrations/                  # Framework Integrations (Standalone, Minimalist)
│   ├── __init__.py                # Top-level exports with graceful ImportError fallbacks
│   ├── google_sdk/                # Google Antigravity Python SDK integration
│   │   ├── __init__.py
│   │   └── google_sdk_integration.py # GoogleSDKConfig & create_agent factory
│   ├── google_adk/                # Google Agent Development Kit (ADK) integration
│   │   ├── __init__.py
│   │   └── google_adk_integration.py # GoogleADKConfig & GoogleADKAgent runner
│   └── llama_index/               # LlamaIndex Framework integration
│       ├── __init__.py
│       └── llama_index_integration.py # LlamaIndexConfig & HebrasLLM (CustomLLM)
│
├── scripts/                       # Developer & Test Tools
│   ├── test_cli.py                # Interactive CLI tool to test chat, stream, schema, multi-turn
│   ├── test_sdk.py                # Direct local SDK agent test script
│   └── antigravity_sdk_example.py # Example script for google-antigravity Python SDK integration
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
    │   ├── test_antigravity_agent.py # End-to-end tests for google-antigravity SDK Agent workflows
    │   ├── test_chat_endpoint.py  # Tests for /v1/chat/completions (sync, stream, multi-turn)
    │   └── test_models_endpoint.py# Tests for /v1/models dynamic clean model discovery
    └── unit/
        ├── __init__.py
        ├── test_agy_interactive.py# Unit tests for InteractiveSession & transcript sync
        ├── test_agy_process.py    # Unit tests for run_agy and stream_agy
        ├── test_ansi_utils.py     # Unit tests for ANSI stripping & chrome extraction
        ├── test_antigravity_compatibility.py # Unit tests for Antigravity SDK schema compatibility
        ├── test_google_adk.py     # Unit test for Google ADK integration
        ├── test_google_sdk.py     # Unit test for Google Antigravity SDK integration
        ├── test_llama_index.py    # Unit test for LlamaIndex HebrasLLM CustomLLM integration
        ├── test_logging_dev_level.py # Unit tests for DEV log level & reflection extraction
        ├── test_safe_runner.py    # Unit tests for safe_run_command & timeout enforcement
        ├── test_session.py        # Unit tests for AgySession lifecycle
        ├── test_session_manager.py# Unit tests for SessionManager pool & eviction
        ├── test_session_manager_concurrency.py # Concurrent session creation/deletion tests
        ├── test_turn_logger.py    # Unit tests for turn logger & evaluation formatting
        └── test_types.py          # Unit tests for Pydantic type conversions & aliases
```

---

## 4. Configuration & Defaults

Settings are managed in `backend/config.py` using `pydantic-settings`.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `HEBRAS_HOST` | `str` | `"127.0.0.1"` | Host to bind the API server |
| `HEBRAS_PORT` | `int` | `8000` | Port to bind the API server |
| `HEBRAS_AGY_BINARY` | `str` | `"agy"` | Path or name of the agy CLI binary |
| `HEBRAS_AGY_DEFAULT_AGENT` | `str` | `"default"` | Default agent persona if unspecified |
| `HEBRAS_AGY_DEFAULT_MODEL` | `str` | `"Gemini 3.7 Flash"` | Default clean model name |
| `HEBRAS_AGY_DEFAULT_REFLECTION` | `str` | `"high"` | Default reflection level (`high`, `medium`, `low`) |
| `HEBRAS_LOG_LEVEL` | `str` | `"INFO"` | Log level: `INFO`, `DEBUG`, or `DEV` (records all messages & reflection) |
| `HEBRAS_LOG_TIMEZONE` | `str | None` | `None` | Timezone (e.g. `Europe/Paris`, default: host local timezone) |
| `HEBRAS_MODEL_CACHE_TTL` | `int` | `300` | In-memory cache TTL for discovered models (seconds) |

---

## 5. Development Workflows & Commands

### 1. Running Automated Tests
```bash
pytest -v
```

### 2. Interactive Test CLI
```bash
python scripts/test_cli.py
```

Commands available in `test_cli.py`:
- `agents`: List discovered agent personas (`GET /v1/agents`).
- `agent <name>`: Switch active agent persona.
- `models`: List discovered clean LLM models (`GET /v1/models`).
- `model <name>`: Switch active clean LLM model.
- `level <low|medium|high>`: Switch reflection level.
- `chat <prompt>`: Send non-streaming chat completion.
- `stream <prompt>`: Send streaming chat completion via SSE.
- `schema <prompt>`: Send completion with JSON Schema enforcement.
- `multi [stream|sync]`: Start an interactive multi-turn conversation (defaults to real-time streaming).

### 3. Running google-antigravity SDK Example
```bash
python scripts/antigravity_sdk_example.py
python scripts/antigravity_sdk_example.py --tools
```

---

## 6. Engineering Standards & Definition of Done

### Real Verification Over Mocks
- **Mocks Are Not Verification**: Mock tests are never a "Definition of Done". Unit test stubs and mock assertions only verify internal code paths, not actual operational correctness.
- **Real In/Out Verification Required**: Only real input/output executions (against live CLI binaries, actual subprocesses, real HTTP endpoints, and verifying actual on-disk logs and output artifacts) qualify as successful completion of a task.
- **Verification is Primordial**: Always run real execution tests, inspect the produced logs and system responses, and confirm behavior end-to-end before concluding any task.

### Artifact Link Formatting Rule
- **Canonical `.brain` Links**: When referencing artifacts (plans, walkthroughs, reports) in chat responses, format markdown links using the canonical absolute path `file:///home/vscode/.gemini/antigravity-cli/brain/<conversation_id>/<filename>.md` so that VS Code resolves the file directly.
- **Cmd+Click Navigation**: This ensures links resolve cleanly inside VS Code editor tabs when using `Cmd+Click` (macOS) or `Ctrl+Click` (Linux/Windows).

### Top-Level Imports Invariant
- **No Inline / Nested Imports**: All `import` and `from ... import ...` statements must be placed strictly at the top of the Python file (module scope). Never import modules inside function bodies, methods, or class definitions. Handle optional imports with top-level `try...except ImportError` guards.


