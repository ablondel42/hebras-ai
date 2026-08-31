"""POST /v1/chat/completions — OpenAI-compatible chat completions endpoint."""
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.agy_interactive import InteractiveSession, InteractiveSessionError
from backend.agy_process import AgyProcessError, run_agy, stream_agy
from backend.config import settings
from backend.session import AgySession
from backend.session_manager import SessionManager, SessionNotFound, SessionPoolFull
from backend.types import (
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    DeltaContent,
    StreamChoice,
    UsageInfo,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_session_manager(request: Request) -> SessionManager:
    """Dependency helper to get SessionManager from app state."""
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="SessionManager not initialized")
    return manager


def _extract_prompt_and_system(request: ChatCompletionRequest) -> tuple[str, str | None]:
    """Extract the user prompt and system instruction from the messages array.

    Combines all system/developer messages into a system prefix, and uses
    the last user message as the prompt.

    Args:
        request: The chat completion request.

    Returns:
        Tuple of (prompt, system_message). prompt is empty if no user message found.
    """
    system_parts: list[str] = []
    user_prompt: str = ""
    has_user_message: bool = False

    for msg in request.messages:
        if msg.role in ("system", "developer"):
            if msg.content:
                system_parts.append(msg.content)
        elif msg.role == "user":
            user_prompt = msg.content or ""
            has_user_message = True

    system_message = "\n".join(system_parts) if system_parts else None

    # Only combine system message into prompt if there's a user message
    if not has_user_message:
        return "", system_message

    if system_message:
        user_prompt = f"[System Instructions]\n{system_message}\n\n[User Request]\n{user_prompt}"

    return user_prompt, system_message


def _extract_agent(model: str) -> str:
    """Extract agent name from model ID.

    Args:
        model: Model ID string (e.g., 'default', 'code-reviewer').

    Returns:
        Agent name.
    """
    if not model or not model.strip():
        return settings.agy_default_agent
    if model.startswith("hebras-interactive-"):
        return model[len("hebras-interactive-"):]
    elif model.startswith("hebras-"):
        return model[len("hebras-"):]
    elif model.startswith("interactive-"):
        return model[len("interactive-"):]
    return model


def _extract_json_schema(request: ChatCompletionRequest) -> dict[str, Any] | None:
    """Extract JSON schema from response_format if present.

    Args:
        request: The chat completion request.

    Returns:
        JSON schema dict or None.
    """
    if not request.response_format:
        return None
    if request.response_format.type == "json_schema" and request.response_format.json_schema:
        return request.response_format.json_schema.schema_
    return None


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    sm: SessionManager = Depends(get_session_manager),
):
    """OpenAI-compatible chat completions endpoint.

    Supports streaming (SSE), non-streaming, and persistent interactive (PTY) modes.
    Maps the model field to agy agent names directly.
    """
    agent = _extract_agent(request.model)
    prompt, _ = _extract_prompt_and_system(request)
    json_schema = _extract_json_schema(request)

    if not prompt:
        raise HTTPException(status_code=400, detail="No user message found in messages array")

    # Resolve or create session for multi-turn
    session = None
    if request.conversation_id:
        try:
            session = await sm.get_session(request.conversation_id)
        except SessionNotFound:
            logger.debug(f"Session {request.conversation_id} not found, creating new")

    if not session:
        try:
            session = await sm.create_session(
                agent=agent,
                workspace=request.workspace or settings.agy_default_workspace,
            )
            if request.conversation_id:
                session.conversation_id = request.conversation_id
        except SessionPoolFull as e:
            raise HTTPException(status_code=429, detail=str(e))

    session.touch()

    is_interactive = (
        request.interactive
        or request.model.startswith("interactive-")
        or request.model.startswith("hebras-interactive-")
    )

    logger.info(
        f"Processing chat completion request: prompt_length={len(prompt)} "
        f"agent='{agent}' conversation_id='{session.conversation_id}' "
        f"stream={request.stream} interactive={is_interactive}"
    )

    if is_interactive:
        return await _handle_interactive(request, session, prompt, agent, json_schema)
    elif request.stream:
        return await _handle_streaming(request, session, prompt, agent, json_schema)
    else:
        return await _handle_non_streaming(request, session, prompt, agent, json_schema)


async def _handle_non_streaming(
    request: ChatCompletionRequest,
    session: AgySession,
    prompt: str,
    agent: str,
    json_schema: dict | None,
) -> ChatCompletionResponse:
    """Handle non-streaming chat completion."""
    try:
        result = await run_agy(
            prompt=prompt,
            agent=agent,
            json_schema=json_schema,
            conversation_id=session.conversation_id,
            workspace=session.workspace,
            model=settings.agy_default_model,
        )
    except AgyProcessError as e:
        logger.error(f"agy process error: {e}", extra={"stderr": e.stderr})
        raise HTTPException(status_code=502, detail=f"AGY execution failed: {e}")

    # Update session with conversation_id from agy response
    if result.get("conversation_id"):
        session.conversation_id = result["conversation_id"]

    # Extract response text
    response_text = result.get("response", "")
    if isinstance(response_text, dict):
        response_text = json.dumps(response_text)

    logger.info(
        f"Non-streaming completion finished: conversation_id='{session.conversation_id}' "
        f"response_length={len(response_text)}"
    )

    # Extract usage info if available
    usage_data = result.get("usage", {})
    usage = UsageInfo(
        prompt_tokens=usage_data.get("input_tokens", 0),
        completion_tokens=usage_data.get("output_tokens", 0),
        total_tokens=usage_data.get("total_tokens", 0),
    )

    return ChatCompletionResponse(
        model=agent,
        choices=[
            Choice(
                message=ChatCompletionMessage(content=response_text),
                finish_reason="stop",
            )
        ],
        usage=usage,
        system_fingerprint=session.conversation_id or session.session_id,
    )


async def _handle_streaming(
    request: ChatCompletionRequest,
    session: AgySession,
    prompt: str,
    agent: str,
    json_schema: dict | None,
) -> StreamingResponse:
    """Handle streaming chat completion via SSE."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    model = agent

    async def event_generator():
        collected_text_parts: list[str] = []

        # First chunk: role indicator
        first_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[StreamChoice(delta=DeltaContent(role="assistant", content=""))],
            system_fingerprint=session.conversation_id or session.session_id,
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        try:
            async for event in stream_agy(
                prompt=prompt,
                agent=agent,
                json_schema=json_schema,
                conversation_id=session.conversation_id,
                workspace=session.workspace,
                model=settings.agy_default_model,
            ):
                # agy NDJSON uses "event" (e.g. "init", "step_update", "result"), fallback to "type"
                event_name = event.get("event") or event.get("type", "")

                # Extract conversation_id if present at top level or in nested objects
                cid = (
                    event.get("conversation_id")
                    or event.get("init", {}).get("conversation_id")
                    or event.get("result", {}).get("conversation_id")
                )
                if cid:
                    session.conversation_id = cid

                if event_name == "step_update":
                    step_data = event.get("step_update", {})
                    # agy puts text deltas in step_update.text_delta
                    content = step_data.get("text_delta") or event.get("content", "")
                    if content:
                        collected_text_parts.append(content)
                        chunk = ChatCompletionChunk(
                            id=completion_id,
                            created=created,
                            model=model,
                            choices=[StreamChoice(delta=DeltaContent(content=content))],
                            system_fingerprint=session.conversation_id or session.session_id,
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                elif event_name == "result":
                    res_data = event.get("result", {})
                    usage_data = res_data.get("usage", {})
                    usage = UsageInfo(
                        prompt_tokens=usage_data.get("input_tokens", 0),
                        completion_tokens=usage_data.get("output_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    )
                    # Final chunk with finish_reason
                    final_chunk = ChatCompletionChunk(
                        id=completion_id,
                        created=created,
                        model=model,
                        choices=[StreamChoice(
                            delta=DeltaContent(),
                            finish_reason="stop",
                        )],
                        usage=usage,
                        system_fingerprint=session.conversation_id or session.session_id,
                    )
                    yield f"data: {final_chunk.model_dump_json()}\n\n"

                # Fallback support for generic stream-json schemas ("text-delta" and "terminal_result")
                elif event_name == "text-delta":
                    content = event.get("content", "")
                    if content:
                        collected_text_parts.append(content)
                        chunk = ChatCompletionChunk(
                            id=completion_id,
                            created=created,
                            model=model,
                            choices=[StreamChoice(delta=DeltaContent(content=content))],
                            system_fingerprint=session.conversation_id or session.session_id,
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

        except AgyProcessError as e:
            logger.error(f"agy stream error: {e}")
            error_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=model,
                choices=[StreamChoice(
                    delta=DeltaContent(content=f"\n\n[Error: {e}]"),
                    finish_reason="stop",
                )],
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

        full_response = "".join(collected_text_parts)
        logger.info(
            f"Streaming completion finished: conversation_id='{session.conversation_id}' "
            f"response='{full_response[:120]}...'"
        )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _handle_interactive(
    request: ChatCompletionRequest,
    session: AgySession,
    prompt: str,
    agent: str,
    json_schema: dict | None,
) -> ChatCompletionResponse:
    """Handle interactive PTY-backed chat completion.

    Creates or reuses a persistent agy TUI session.
    Returns standard OpenAI-format response with clean text.
    """
    if session.interactive is None or not session.interactive.is_alive():
        interactive = InteractiveSession(
            agent=agent,
            workspace=session.workspace or settings.agy_default_workspace,
            mode=request.mode,
            auto_approve=request.dangerously_skip_permissions,
            conversation_id=session.conversation_id,
        )
        try:
            await interactive.start()
        except InteractiveSessionError as e:
            logger.error(f"Failed to start interactive agy session: {e}")
            raise HTTPException(status_code=502, detail=f"Interactive agy execution failed: {e}")

        session.interactive = interactive
        session.conversation_id = interactive.conversation_id or session.conversation_id
        session.mode = "interactive"

    try:
        response_text = await session.interactive.send_message(prompt)
    except InteractiveSessionError as e:
        logger.error(f"Interactive agy session error: {e}")
        raise HTTPException(status_code=502, detail=f"Interactive agy session error: {e}")

    session.touch()

    logger.info(
        f"Interactive completion finished: session_id='{session.session_id}' "
        f"response='{response_text[:120]}...'"
    )

    return ChatCompletionResponse(
        model=agent,
        choices=[
            Choice(
                message=ChatCompletionMessage(content=response_text),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(),
        system_fingerprint=session.session_id,
    )
