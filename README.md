# hebras-ai

An OpenAI-compatible REST API backend adapter over Google Antigravity (`agy` CLI).

---

## Key Features

- **OpenAI Compatible**: Seamlessly integrates with tools and LLM frameworks using standard `/v1/chat/completions` and `/v1/models` endpoints.
- **google-antigravity SDK Provider**: Acts as a local LLM engine for the official `google-antigravity` Python SDK via `LocalOpenAIAgentConfig`.
- **Natural Agent Discovery**: Automatically scans `.agents/agents/` to expose local custom agents directly by name.
- **Three Execution Modes**:
  1. Non-streaming JSON (`stream=false`).
  2. Real-time streaming SSE (`stream=true`).
  3. Persistent interactive sessions via PTY (`interactive=true`).

---

## Quickstart

### 1. Install Dependencies
```bash
python3 -m pip install -r requirements.txt
# or with development tools:
python3 -m pip install -e ".[dev]"
```

### 2. Start the Backend Server
```bash
# Run using uvicorn
uvicorn backend.main:app --reload --port 8000

# Or run using Python module
python3 -m backend.main
```

---

## Using with `google-antigravity` Python SDK

You can route `google-antigravity` agent workflows directly to `hebras-ai` running on `localhost:8000` using `LocalOpenAIAgentConfig`:

```python
import asyncio
import sys
from google.antigravity import Agent, LocalOpenAIAgentConfig
from google.antigravity.hooks import policy

async def main():
    # Configure the agent to route to localhost:8000
    config = LocalOpenAIAgentConfig(
        base_url="http://localhost:8000/v1",
        model="Gemini 3.7 Flash",
        policies=[policy.allow_all()],
    )

    async with Agent(config) as agent:
        response = await agent.chat("Explain quantum computing in 2 sentences.")
        async for token in response:
            sys.stdout.write(token)
            sys.stdout.flush()
        print()

if __name__ == "__main__":
    asyncio.run(main())
```

### Run the Example Script
```bash
# Basic streaming agent workflow:
python3 scripts/antigravity_sdk_example.py

# Agent workflow with custom Python tools:
python3 scripts/antigravity_sdk_example.py --tools
```

---

## Developer Tools & Testing

### Interactive Test CLI
```bash
python3 scripts/test_cli.py
```

### Run Tests
```bash
pytest -v
```
