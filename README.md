# hebras-ai

An OpenAI-compatible REST API backend adapter over Google Antigravity (`agy` CLI).

---

## Key Features

- **OpenAI Compatible**: Seamlessly integrates with tools and LLM frameworks using standard `/v1/chat/completions` and `/v1/models` endpoints.
- **Natural Agent Discovery**: Automatically scans `.agents/agents/` to expose local custom agents directly by name.
- **Three Execution Modes**:
  1. Non-streaming JSON (`stream=false`).
  2. Real-time streaming SSE (`stream=true`).
  3. Persistent interactive sessions via PTY (`interactive=true`).

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
# or with dev tools:
pip install -e ".[dev]"
```

### 2. Start the Backend Server
```bash
# Run using uvicorn
uvicorn backend.main:app --reload --port 8000

# Or run using Python module
python -m backend.main
```

### 3. Run the Interactive Test CLI
```bash
python scripts/test_cli.py
```

### 4. Run Tests
```bash
pytest -v
```
