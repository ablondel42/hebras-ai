"""Structured JSON logging configuration and file handler setup with DEV log level support."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from backend.config import settings
from backend.turn_logger import get_log_datetime, is_test_environment

DEV_LEVEL_NUM = 5
logging.addLevelName(DEV_LEVEL_NUM, "DEV")


def _dev_log(self, message, *args, **kws):
    """Log a message at custom DEV level (5)."""
    if self.isEnabledFor(DEV_LEVEL_NUM):
        self._log(DEV_LEVEL_NUM, message, args, **kws)


# Bind .dev() method to logging.Logger
logging.Logger.dev = _dev_log  # type: ignore[attr-defined]


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with DEV message and reflection support."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": get_log_datetime().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include standard and DEV-specific extra fields
        extra_keys = (
            "session_id",
            "conversation_id",
            "turn",
            "agent",
            "model",
            "target_model",
            "reflection_level",
            "mode",
            "request_messages",
            "thinking",
            "response",
            "duration_s",
            "duration_ms",
            "usage",
        )
        for key in extra_keys:
            if hasattr(record, key):
                val = getattr(record, key)
                if val is not None:
                    log_entry[key] = val

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root logger with stdout and log/hebras.log file output."""
    root = logging.getLogger()

    log_level_str = settings.log_level.upper()
    if log_level_str == "DEV":
        root.setLevel(DEV_LEVEL_NUM)
    else:
        root.setLevel(getattr(logging, log_level_str, logging.INFO))

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
