"""Structured JSON logging configuration and file handler setup with user timezone."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from backend.config import settings
from backend.turn_logger import get_log_datetime, is_test_environment


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with local timezone timestamps."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": get_log_datetime().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include extra fields (session_id, conversation_id, etc.)
        for key in ("session_id", "conversation_id", "agent", "duration_ms"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure root logger with stdout and log/hebras.log file output."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper()))
    root.handlers.clear()

    # Formatter selection
    if settings.log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler (only when not in test environment)
    if not is_test_environment():
        try:
            log_dir = Path(settings.agy_log_dir).expanduser().resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "hebras.log",
                maxBytes=10_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"Failed to setup file logger: {e}\n")
