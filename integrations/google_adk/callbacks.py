"""Official Google ADK lifecycle callbacks and logging plugin for deep debugging."""

from __future__ import annotations

import time
import traceback
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from integrations.google_adk.logging import format_adk_tree, get_adk_logger

agent_logger = get_adk_logger("agent")
model_logger = get_adk_logger("model")
tool_logger = get_adk_logger("tools")

# Contextual timer storage
_TIMER_CACHE: dict[str, float] = {}


async def adk_before_agent_callback(callback_context: Any) -> None:
    """Invoked before the agent executes a turn."""
    agent_name = getattr(getattr(callback_context, "agent", None), "name", "root_agent")
    session_id = getattr(callback_context, "session_id", "local")
    _TIMER_CACHE[f"agent_{session_id}"] = time.perf_counter()

    agent_logger.info(
        format_adk_tree(
            f"Agent '{agent_name}' turn starting",
            [
                ("Agent Name", agent_name),
                ("Session ID", session_id),
            ],
        )
    )


async def adk_after_agent_callback(callback_context: Any) -> Any:
    """Invoked after the agent finishes a turn."""
    agent_name = getattr(getattr(callback_context, "agent", None), "name", "root_agent")
    session_id = getattr(callback_context, "session_id", "local")
    start_t = _TIMER_CACHE.pop(f"agent_{session_id}", None)
    dur = (time.perf_counter() - start_t) * 1000.0 if start_t else None

    agent_logger.info(
        format_adk_tree(
            f"Agent '{agent_name}' turn completed",
            [
                ("Agent Name", agent_name),
                ("Session ID", session_id),
            ],
            duration_ms=dur,
        )
    )
    return None


async def adk_before_model_callback(callback_context: Any, llm_request: Any) -> Any:
    """Invoked before calling the LLM."""
    model_name = getattr(llm_request, "model", "Unknown")
    req_id = id(llm_request)
    _TIMER_CACHE[f"model_{req_id}"] = time.perf_counter()

    contents = getattr(llm_request, "contents", [])
    content_count = len(contents) if isinstance(contents, list) else 1

    model_logger.debug(
        format_adk_tree(
            f"Model Request -> {model_name}",
            [
                ("Model Target", model_name),
                ("Content Turns", content_count),
            ],
        )
    )
    return None


async def adk_after_model_callback(callback_context: Any, llm_response: Any) -> Any:
    """Invoked after receiving the LLM response."""
    req_id = id(getattr(callback_context, "current_request", None))
    start_t = _TIMER_CACHE.pop(f"model_{req_id}", None)
    dur = (time.perf_counter() - start_t) * 1000.0 if start_t else None

    tool_calls = getattr(llm_response, "function_calls", []) or []
    tool_call_names = [getattr(tc, "name", str(tc)) for tc in tool_calls]

    model_logger.debug(
        format_adk_tree(
            "Model Response Received",
            [
                ("Tool Calls Generated", len(tool_calls)),
                ("Tools Requested", tool_call_names or "(None)"),
            ],
            duration_ms=dur,
        )
    )
    return None


async def adk_on_model_error_callback(
    callback_context: Any, llm_request: Any, error: Exception
) -> None:
    """Invoked when model communication fails."""
    model_name = getattr(llm_request, "model", "Unknown")
    tb = traceback.format_exc()

    model_logger.error(
        format_adk_tree(
            f"Model Execution Error ({model_name})",
            [
                ("Model Target", model_name),
                ("Exception", f"{type(error).__name__}: {error}"),
                ("Traceback", tb),
            ],
        )
    )


async def adk_before_tool_callback(
    tool: Any, args: dict[str, Any], tool_context: Any
) -> Any:
    """Invoked before executing an ADK tool."""
    tool_name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
    tool_id = f"tool_{tool_name}_{id(args)}"
    _TIMER_CACHE[tool_id] = time.perf_counter()

    fields: list[tuple[str, Any]] = [("Tool Name", tool_name)]
    for k, v in list(args.items())[:5]:
        val_str = str(v)
        fields.append((f"Arg: {k}", val_str[:120] + "..." if len(val_str) > 120 else val_str))

    tool_logger.info(
        format_adk_tree(
            f"Tool Execution Start: {tool_name}",
            fields,
        )
    )
    return None


async def adk_after_tool_callback(
    tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
) -> Any:
    """Invoked after executing an ADK tool."""
    tool_name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
    tool_id = f"tool_{tool_name}_{id(args)}"
    start_t = _TIMER_CACHE.pop(tool_id, None)
    dur = (time.perf_counter() - start_t) * 1000.0 if start_t else None

    # Summarize response
    if isinstance(tool_response, dict):
        status = tool_response.get("status", "completed")
        summary_fields = [("Status", status)]
        if "message" in tool_response:
            summary_fields.append(("Message", tool_response["message"]))
        if "valid" in tool_response:
            summary_fields.append(("Valid", tool_response["valid"]))
        if "overall_roi_score" in tool_response:
            summary_fields.append(("ROI Score", tool_response["overall_roi_score"]))
    else:
        resp_str = str(tool_response)
        summary_fields = [
            ("Result", resp_str[:120] + "..." if len(resp_str) > 120 else resp_str)
        ]

    tool_logger.info(
        format_adk_tree(
            f"Tool Execution Complete: {tool_name}",
            summary_fields,
            duration_ms=dur,
        )
    )
    return None


async def adk_on_tool_error_callback(
    tool: Any, args: dict[str, Any], tool_context: Any, error: Exception
) -> None:
    """Invoked when a tool raises an unhandled exception."""
    tool_name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
    tb = traceback.format_exc()

    tool_logger.error(
        format_adk_tree(
            f"Tool Execution FAILED: {tool_name}",
            [
                ("Tool Name", tool_name),
                ("Exception", f"{type(error).__name__}: {error}"),
                ("Traceback", tb),
            ],
        )
    )


class ADKDebugLoggingPlugin(BasePlugin):
    """Google ADK Plugin that attaches debugging hooks across all agents and tools."""

    def __init__(self, name: str = "adk_debug_logging") -> None:
        super().__init__(name=name)

    async def before_agent_callback(self, *, callback_context: Any) -> None:
        await adk_before_agent_callback(callback_context)

    async def after_agent_callback(self, *, callback_context: Any) -> Any:
        return await adk_after_agent_callback(callback_context)

    async def before_model_callback(self, *, callback_context: Any, llm_request: Any) -> Any:
        return await adk_before_model_callback(callback_context, llm_request)

    async def after_model_callback(self, *, callback_context: Any, llm_response: Any) -> Any:
        return await adk_after_model_callback(callback_context, llm_response)

    async def on_model_error_callback(
        self, *, callback_context: Any, llm_request: Any, error: Exception
    ) -> None:
        await adk_on_model_error_callback(callback_context, llm_request, error)

    async def before_tool_callback(
        self, *, tool: Any, args: dict[str, Any], tool_context: Any
    ) -> Any:
        return await adk_before_tool_callback(tool, args, tool_context)

    async def after_tool_callback(
        self, *, tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
    ) -> Any:
        return await adk_after_tool_callback(tool, args, tool_context, tool_response)

    async def on_tool_error_callback(
        self, *, tool: Any, args: dict[str, Any], tool_context: Any, error: Exception
    ) -> None:
        await adk_on_tool_error_callback(tool, args, tool_context, error)
