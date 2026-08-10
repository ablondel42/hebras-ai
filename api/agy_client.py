# agy_client.py
import json
from pathlib import Path
import subprocess
import time
from typing import Optional, Any, Dict, Tuple

from click import prompt


def get_help():
    cmd = ["agy", "-h"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return proc.stderr

def init_session(
    prompt: str,
    conversation_id: str | None,
    timeout: int = 120,
    json_schema: Dict[str, Any] = {},
    cwd: str = "/Users/arnaud/dev/_fullstack-ai-python/hebras-ai"
) -> Tuple[str, str, int, Optional[Dict[str, Any]]]:
    """
    Run agy --print and return (stdout, stderr, returncode, structured_output, duration).
    """
    cmd = [
        "agy", 
        "--print", prompt,
        "--agent", "read",
        "--output-format", "json",
        "--add-dir", str(Path(cwd).expanduser().resolve()),
    ]

    if json_schema:
        cmd.extend(["--json-schema", json.dumps(json_schema)])
    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    start = time.time()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=Path(cwd).expanduser().resolve(),
    )

    structured = None
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            structured = data.get("structured_output")
        except Exception:
            pass

    return proc.stdout, proc.stderr, proc.returncode, structured