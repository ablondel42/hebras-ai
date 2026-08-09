# agy_client.py
import json
import subprocess
import time
from typing import Optional, Any, Dict, Tuple

def init_session(
    prompt: str,
    conversation_id: str | None,
    timeout: int = 120,
    json_schema: Dict[str, Any] = {},
) -> Tuple[str, str, int, Optional[Dict[str, Any]]]:
    """
    Run agy -p and return (stdout, stderr, returncode, structured_output, duration).
    """
    cmd = [
        "agy", "-p", prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions"
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
    )

    structured = None
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            structured = data.get("structured_output")
        except Exception:
            pass

    return proc.stdout, proc.stderr, proc.returncode, structured