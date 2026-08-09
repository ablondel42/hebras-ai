from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .agy_client import init_session as agy_init_session
except ImportError:
    from agy_client import init_session as agy_init_session

from schemas import init_session_schema

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


@app.post("/init-session")
async def init_session_prompt(options: InitSessionOptions):
    stdout, stderr, returncode, structured_output = agy_init_session(
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

