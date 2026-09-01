"""Example script demonstrating google-antigravity Python SDK with hebras-ai.

Shows how to route agent workflows, streaming responses, thinking,
and custom Python tools to a local hebras-ai server on http://localhost:8000/v1.

Prerequisites:
  1. Start hebras-ai server:
     python3 -m backend.main  (or uvicorn backend.main:app --port 8000)
  2. Run this script:
     python3 scripts/antigravity_sdk_example.py
"""
import argparse
import asyncio
import sys

from google.antigravity import Agent, LocalOpenAIAgentConfig
from google.antigravity.hooks import policy


# ── Example Custom Tools for the Agent ──────────────────────────────────────────


def calculate_expression(expression: str) -> str:
    """Safely evaluates a basic math expression (e.g. '123 * 456').

    Args:
        expression: The mathematical expression string.
    """
    try:
        allowed = set("0123456789+-*/(). %")
        if not all(c in allowed for c in expression):
            return "Error: Invalid characters in mathematical expression."
        # pylint: disable=eval-used
        result = eval(expression, {"__builtins__": None}, {})
        return f"Result: {result}"
    except Exception as e:
        return f"Error evaluating expression: {e}"


def get_current_time_zone() -> str:
    """Returns the local timezone offset and description."""
    import time
    return f"Local timezone: {time.tzname[0]}, offset: {time.timezone // 3600} hours"


# ── Main Agent Workflows ───────────────────────────────────────────────────────


async def run_basic_streaming(base_url: str, model: str, prompt: str):
    """Run basic agent prompt with token streaming routed through hebras-ai."""
    print("=" * 70)
    print(f"[1] Running basic streaming agent workflow...")
    print(f"    Target Server : {base_url}")
    print(f"    Target Model  : {model}")
    print(f"    Prompt        : {prompt}")
    print("=" * 70)

    config = LocalOpenAIAgentConfig(
        base_url=base_url,
        model=model,
        system_instructions="You are a knowledgeable, concise AI assistant.",
        policies=[policy.allow_all()],
    )

    async with Agent(config) as agent:
        response = await agent.chat(prompt)

        print("\nAgent Response:")
        async for token in response:
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n")


async def run_agent_with_tools(base_url: str, model: str):
    """Run agent workflow with custom tools and policy approval."""
    print("=" * 70)
    print(f"[2] Running agent with custom Python tools...")
    print(f"    Registered Tools: calculate_expression, get_current_time_zone")
    print("=" * 70)

    config = LocalOpenAIAgentConfig(
        base_url=base_url,
        model=model,
        system_instructions="You are a helpful assistant with math and time tools.",
        tools=[calculate_expression, get_current_time_zone],
        policies=[policy.allow_all()],
    )

    async with Agent(config) as agent:
        prompt = "What is 48291 multiplied by 318? Also what is the local timezone?"
        print(f"\nUser: {prompt}")
        response = await agent.chat(prompt)

        print("\nAgent Response:")
        async for token in response:
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n")


async def main():
    parser = argparse.ArgumentParser(description="google-antigravity SDK + hebras-ai Example")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1", help="hebras-ai API base URL")
    parser.add_argument("--model", default="Gemini 3.7 Flash", help="LLM model identifier")
    parser.add_argument("--prompt", default="Explain what Google Antigravity is in 2 concise sentences.", help="Prompt to test")
    parser.add_argument("--tools", action="store_true", help="Run tool calling demonstration")
    args = parser.parse_args()

    try:
        if args.tools:
            await run_agent_with_tools(args.base_url, args.model)
        else:
            await run_basic_streaming(args.base_url, args.model, args.prompt)
    except Exception as e:
        print(f"\n[!] Error running agent: {e}", file=sys.stderr)
        print("\nTip: Make sure hebras-ai server is running on the specified base-url:")
        print(f"     python3 -m uvicorn backend.main:app --port 8000")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
