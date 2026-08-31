"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # AGY CLI
    agy_binary: str = "agy"
    agy_default_agent: str = "default"
    agy_default_model: str = "Gemini 3.7 Flash"
    agy_default_reflection: str = "high"  # "low", "medium", "high"
    agy_default_timeout: int = 120
    agy_default_workspace: str = "."
    agy_agents_dir: str = ".agents/agents"
    agy_default_mode: str | None = None
    agy_dangerously_skip_permissions: bool = False
    agy_interactive_timeout: int = 180
    agy_log_dir: str = "log"
    model_cache_ttl: int = 300  # seconds

    # Session Pool
    max_sessions: int = 10
    session_idle_timeout: int = 600  # seconds

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    log_timezone: str | None = None  # None = host local timezone, e.g. "Europe/Paris"

    # Auth (future)
    # api_key: str | None = None

    model_config = {"env_file": [".env", "dev.env"], "env_prefix": "HEBRAS_", "extra": "ignore"}


settings = Settings()
