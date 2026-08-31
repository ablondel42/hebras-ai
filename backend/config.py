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
    agy_default_model: str = "Gemini 3.6 Flash (High)"
    agy_available_models: list[str] = [
        "Gemini 3.6 Flash (High)",
        "Gemini 3.5 Pro",
        "Gemini 3.5 Flash",
        "Claude 3.7 Sonnet",
        "Claude 3.5 Sonnet",
        "GPT-4o",
    ]
    agy_default_timeout: int = 120
    agy_default_workspace: str = "."
    agy_agents_dir: str = ".agents/agents"
    agy_default_mode: str | None = None
    agy_dangerously_skip_permissions: bool = False
    agy_interactive_timeout: int = 180
    agy_log_dir: str = "log"

    # Session Pool
    max_sessions: int = 10
    session_idle_timeout: int = 600  # seconds

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"

    # Auth (future)
    # api_key: str | None = None

    model_config = {"env_file": "dev.env", "env_prefix": "HEBRAS_"}


settings = Settings()
