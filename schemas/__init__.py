from __future__ import annotations

from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent
init_session_schema = json.loads((BASE_DIR / "init_session.json").read_text(encoding="utf-8"))
