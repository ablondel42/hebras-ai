from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any
from api.agy_client import get_help, init_session
from schemas.init_session_schema import init_session_schema
app = FastAPI()


class InitSessionOptions(BaseModel):
    prompt: str
    cwd: str = "."
    conversation_id: str | None = None
    timeout: int = 120
    json_schema: dict[str, Any] = {}


@app.get("/")
async def root():
    return {"message": "root"}


@app.get("/help")
async def help():
    help_text = get_help()
    print("Help text:", help_text, flush=True)
    return help_text


@app.post("/init-session")
async def init_session_prompt(options: InitSessionOptions):
    stdout, stderr, returncode, structured_output = init_session(
        prompt=options.prompt,
        conversation_id=options.conversation_id or "",
        timeout=options.timeout,
        json_schema=options.json_schema or init_session_schema,
    )

    print(json.dumps(json.loads(stdout), indent=2))
    # print(stdout_json)
    # stderr_json = json.dumps(json.loads(stderr), indent=2)
    # print(stderr_json)
    # print(json.dumps(structured_output, indent=2))


    response = {
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "structured_output": structured_output,
    }

    # response_text = json.dumps(response, indent=2, ensure_ascii=False)
    # print(f"Response: {response_text}")
    return response

