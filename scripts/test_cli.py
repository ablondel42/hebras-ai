#!/usr/bin/env python3
"""
hebras-ai Interactive Test CLI

A minimal command-line tool for testing the hebras-ai API server.
Start the server first:  uvicorn backend.main:app --reload --port 8000
Then run this:           python3 test_cli.py
"""
import json

import httpx

# ── Configuration ────────────────────────────────────────────────

BASE_URL = "http://localhost:8080"
DEFAULT_AGENT = "default"

# ── Colors ───────────────────────────────────────────────────────

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
MAGENTA = "\033[35m"

# ── Helpers ──────────────────────────────────────────────────────


def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════╗
║         hebras-ai  ·  Test CLI               ║
╚══════════════════════════════════════════════╝{RESET}
{DIM}Server: {BASE_URL}
Type a command or 'help' to see options.{RESET}
""")


def print_help():
    print(f"""
{BOLD}Available commands:{RESET}

  {GREEN}agents{RESET}                  List available agents
  {GREEN}agent{RESET}  {DIM}<name>{RESET}          Switch active agent (e.g. default, coder)
  {GREEN}chat{RESET}   {DIM}<message>{RESET}        Send a non-streaming chat message
  {GREEN}stream{RESET} {DIM}<message>{RESET}        Send a streaming chat message (SSE)
  {GREEN}schema{RESET} {DIM}<message>{RESET}        Send with JSON schema enforcement
  {GREEN}system{RESET} {DIM}<instruction>{RESET}    Set a system prompt for subsequent messages
  {GREEN}multi{RESET}                   Start an interactive multi-turn conversation
  {GREEN}raw{RESET}                     Send a raw JSON payload
  {GREEN}health{RESET}                  Check if the server is running
  {GREEN}help{RESET}                    Show this help
  {GREEN}quit{RESET} / {GREEN}exit{RESET}            Exit the CLI
""")


def check_server():
    """Check if the server is reachable."""
    try:
        r = httpx.get(f"{BASE_URL}/", timeout=3)
        return r.status_code == 200
    except httpx.ConnectError:
        return False


def pretty_json(data):
    """Pretty-print JSON with colors."""
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    return formatted


def print_response_meta(data):
    """Print response metadata (agent, usage, id)."""
    agent = data.get("model", "?")
    usage = data.get("usage", {})
    comp_id = data.get("id", "?")
    prompt_t = usage.get("prompt_tokens", 0)
    comp_t = usage.get("completion_tokens", 0)
    total_t = usage.get("total_tokens", 0)
    print(f"\n{DIM}── id: {comp_id}  agent: {agent}  tokens: {prompt_t}→{comp_t} ({total_t} total) ──{RESET}")


# ── Commands ─────────────────────────────────────────────────────

def cmd_agents():
    """GET /v1/models (maps to agent listing)"""
    print(f"\n{DIM}GET /v1/models (Listing Agents){RESET}")
    try:
        r = httpx.get(f"{BASE_URL}/v1/models", timeout=10)
        data = r.json()
        models = data.get("data", [])
        print(f"\n{BOLD}Available Agents:{RESET}")
        for m in models:
            agent_name = m['id']
            print(f"  {GREEN}•{RESET} {BOLD}{agent_name}{RESET}")
        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def cmd_chat(message: str, agent: str, system_prompt: str | None = None, stream: bool = False,
             json_schema: dict | None = None, conversation_id: str | None = None):
    """POST /v1/chat/completions"""
    model_id = agent
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model_id,
        "messages": messages,
        "stream": stream,
    }
    if json_schema:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": json_schema,
            },
        }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    mode = "streaming" if stream else "non-streaming"
    print(f"\n{DIM}POST /v1/chat/completions (agent: {agent}, {mode}){RESET}")

    try:
        if stream:
            return _handle_stream(payload, agent)
        else:
            return _handle_non_stream(payload)
    except httpx.ConnectError:
        print(f"{RED}Error: Cannot connect to server at {BASE_URL}{RESET}")
        print(f"{YELLOW}Make sure the server is running: uvicorn backend.main:app --reload --port 8000{RESET}")
        return None
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return None


def _handle_non_stream(payload):
    """Handle non-streaming response."""
    r = httpx.post(f"{BASE_URL}/v1/chat/completions", json=payload, timeout=180)
    if r.status_code != 200:
        print(f"{RED}HTTP {r.status_code}: {r.text}{RESET}")
        return None

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    print(f"{BOLD}{MAGENTA}Assistant:{RESET}")
    print(content)
    print_response_meta(data)

    return data


def _handle_stream(payload, agent_name: str):
    """Handle SSE streaming response."""
    collected_content = ""
    final_data = None
    system_fingerprint = None

    print(f"{BOLD}{MAGENTA}Assistant:{RESET} ", end="", flush=True)

    with httpx.stream("POST", f"{BASE_URL}/v1/chat/completions", json=payload, timeout=180) as r:
        if r.status_code != 200:
            print(f"\n{RED}HTTP {r.status_code}{RESET}")
            return None

        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]  # strip "data: "
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    print(content, end="", flush=True)
                    collected_content += content

                if chunk.get("system_fingerprint"):
                    system_fingerprint = chunk.get("system_fingerprint")

                finish = chunk.get("choices", [{}])[0].get("finish_reason")
                if finish:
                    final_data = chunk
            except json.JSONDecodeError:
                pass

    print()  # newline after stream
    comp_id = "?"
    if final_data:
        comp_id = final_data.get("id", "?")
        print(f"\n{DIM}── id: {comp_id}  agent: {agent_name}  finish: stop ──{RESET}")

    return {
        "id": comp_id,
        "content": collected_content,
        "system_fingerprint": system_fingerprint,
    }


def cmd_multi_turn(agent: str, system_prompt: str | None = None):
    """Interactive multi-turn conversation."""
    print(f"\n{BOLD}Multi-turn conversation (agent: {agent}){RESET} {DIM}(type 'done' to exit){RESET}")
    conversation_id = None
    turn = 0

    while True:
        turn += 1
        try:
            user_input = input(f"\n{CYAN}[Turn {turn}] You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ("done", "exit", "quit"):
            break

        result = cmd_chat(
            message=user_input,
            agent=agent,
            system_prompt=system_prompt if turn == 1 else None,
            conversation_id=conversation_id,
        )
        if result:
            cid = result.get("system_fingerprint")
            if cid:
                conversation_id = cid
                print(f"{DIM}  ↳ conversation_id: {cid}{RESET}")

    print(f"\n{DIM}Conversation ended ({turn - 1} turns){RESET}")


def cmd_raw():
    """Send a raw JSON payload."""
    print(f"\n{DIM}Enter your JSON payload (end with an empty line):{RESET}")
    lines = []
    while True:
        try:
            line = input()
            if not line:
                break
            lines.append(line)
        except EOFError:
            break

    raw = "\n".join(lines)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"{RED}Invalid JSON: {e}{RESET}")
        return

    print(f"\n{DIM}POST /v1/chat/completions{RESET}")
    try:
        r = httpx.post(f"{BASE_URL}/v1/chat/completions", json=payload, timeout=180)
        print(f"\n{DIM}HTTP {r.status_code}{RESET}")
        print(pretty_json(r.json()))
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")


# ── Main Loop ────────────────────────────────────────────────────

def main():
    print_header()

    # Check server
    if not check_server():
        print(f"{YELLOW}⚠  Server not reachable at {BASE_URL}{RESET}")
        print(f"{DIM}Start it with: uvicorn backend.main:app --reload --port 8000{RESET}\n")

    current_agent = DEFAULT_AGENT
    system_prompt = None

    while True:
        try:
            raw_input = input(f"{CYAN}hebras ({current_agent})>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye!{RESET}")
            break

        if not raw_input:
            continue

        parts = raw_input.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            print(f"{DIM}Goodbye!{RESET}")
            break

        elif cmd == "help":
            print_help()

        elif cmd == "health":
            if check_server():
                print(f"{GREEN}✓ Server is running at {BASE_URL}{RESET}")
            else:
                print(f"{RED}✗ Server not reachable at {BASE_URL}{RESET}")

        elif cmd in ("agents", "models"):
            cmd_agents()

        elif cmd in ("agent", "model"):
            if arg:
                current_agent = arg.strip()
                print(f"{GREEN}Switched agent to: {BOLD}{current_agent}{RESET}")
            else:
                print(f"Active agent: {BOLD}{current_agent}{RESET}")

        elif cmd == "system":
            if arg:
                system_prompt = arg
                print(f"{GREEN}System prompt set:{RESET} {DIM}{arg[:80]}{'...' if len(arg) > 80 else ''}{RESET}")
            else:
                if system_prompt:
                    print(f"Current system prompt: {DIM}{system_prompt}{RESET}")
                else:
                    print(f"{DIM}No system prompt set. Usage: system <instruction>{RESET}")

        elif cmd == "chat":
            if not arg:
                print(f"{YELLOW}Usage: chat <message>{RESET}")
                continue
            cmd_chat(arg, current_agent, system_prompt)

        elif cmd == "stream":
            if not arg:
                print(f"{YELLOW}Usage: stream <message>{RESET}")
                continue
            cmd_chat(arg, current_agent, system_prompt, stream=True)

        elif cmd == "schema":
            if not arg:
                print(f"{YELLOW}Usage: schema <message>{RESET}")
                continue
            file_list_schema = {
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                },
                "required": ["files", "summary"],
            }
            cmd_chat(arg, current_agent, system_prompt, json_schema=file_list_schema)

        elif cmd == "multi":
            cmd_multi_turn(current_agent, system_prompt)

        elif cmd == "raw":
            cmd_raw()

        else:
            # Treat unrecognized input as a chat message for convenience
            cmd_chat(raw_input, current_agent, system_prompt)


if __name__ == "__main__":
    main()
