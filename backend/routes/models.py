"""GET /v1/models — Discover available agents as OpenAI-compatible models."""
import logging
from pathlib import Path

from fastapi import APIRouter

from backend.config import settings
from backend.types import ModelInfo, ModelListResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _discover_agents() -> list[ModelInfo]:
    """Scan .agents/agents/ directory for available agent configs.

    Each subdirectory containing a .md file becomes a model.
    Model IDs match the agent directory name directly.

    Returns:
        List of ModelInfo objects for discovered agents.
    """
    agents_dir = Path(settings.agy_agents_dir)
    models: list[ModelInfo] = []

    try:
        if not agents_dir.exists():
            logger.warning("Agents directory not found: %s", agents_dir)
            return models

        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir():
                # Check for a .md config file
                md_files = list(agent_dir.glob("*.md"))
                if md_files:
                    agent_name = agent_dir.name
                    models.append(
                        ModelInfo(
                            id=agent_name,
                            created=int(agent_dir.stat().st_mtime),
                            owned_by="hebras-ai",
                        )
                    )
    except OSError as e:
        logger.error("Error discovering agents in %s: %s", agents_dir, e)

    return models


@router.get("/models")
async def list_models() -> ModelListResponse:
    """List available models (discovered from .agents/agents/).

    Scans the agents directory and returns each configured agent
    as an OpenAI-compatible model entry.
    """
    try:
        models = _discover_agents()
    except Exception as e:
        logger.error("Failed to list models: %s", e)
        models = []

    if not models:
        logger.warning("No agents discovered, returning default model")
        models = [
            ModelInfo(
                id=settings.agy_default_agent,
                owned_by="hebras-ai",
            )
        ]
    return ModelListResponse(data=models)
