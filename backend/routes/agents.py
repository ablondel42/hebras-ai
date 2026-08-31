"""GET /v1/agents — Discover available agent personas and configurations."""
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.config import settings
from backend.types import AgentInfo, AgentListResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Simple parser for YAML frontmatter between --- delimiters."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    frontmatter_text = match.group(1)
    metadata: dict[str, Any] = {}
    current_key = None

    for line in frontmatter_text.splitlines():
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#"):
            continue
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, val = line.split(":", 1)
            current_key = key.strip()
            val_clean = val.strip()
            if val_clean:
                metadata[current_key] = val_clean
            else:
                metadata[current_key] = []
        elif line_strip.startswith("- ") and current_key:
            item = line_strip[2:].strip()
            if isinstance(metadata.get(current_key), list):
                metadata[current_key].append(item)
    return metadata


def discover_agents() -> list[AgentInfo]:
    """Scan .agents/agents/ directory for available agent configurations.

    Returns:
        List of AgentInfo objects for discovered agent profiles.
    """
    agents_dir = Path(settings.agy_agents_dir)
    agents: list[AgentInfo] = []

    try:
        if agents_dir.exists():
            for agent_dir in sorted(agents_dir.iterdir()):
                if agent_dir.is_dir():
                    md_files = list(agent_dir.glob("*.md"))
                    if md_files:
                        primary_md = md_files[0]
                        agent_name = agent_dir.name
                        description = None
                        tools = None
                        cmd_policy = None
                        try:
                            content = primary_md.read_text(encoding="utf-8", errors="replace")
                            meta = _parse_frontmatter(content)
                            description = meta.get("description")
                            tools = meta.get("tools")
                            cmd_policy = meta.get("commandExecutionPolicy")
                        except Exception as e:
                            logger.debug("Could not parse frontmatter for agent %s: %e", agent_name, e)

                        agents.append(
                            AgentInfo(
                                id=agent_name,
                                name=agent_name,
                                description=description,
                                tools=tools if isinstance(tools, list) else None,
                                command_execution_policy=str(cmd_policy) if cmd_policy else None,
                                created=int(primary_md.stat().st_mtime),
                            )
                        )
    except OSError as e:
        logger.error("Error discovering agents in %s: %s", agents_dir, e)

    # Always ensure default agent is included if not in custom agents directory
    agent_ids = {a.id for a in agents}
    if settings.agy_default_agent not in agent_ids:
        agents.insert(
            0,
            AgentInfo(
                id=settings.agy_default_agent,
                name=settings.agy_default_agent,
                description="Default general-purpose Antigravity agent",
                created=0,
            ),
        )

    return agents


@router.get("/agents")
async def list_agents() -> AgentListResponse:
    """List available agent profiles (discovered from .agents/agents/ and built-in defaults)."""
    try:
        agents = discover_agents()
    except Exception as e:
        logger.error("Failed to list agents: %s", e)
        agents = [
            AgentInfo(
                id=settings.agy_default_agent,
                name=settings.agy_default_agent,
                description="Default general-purpose Antigravity agent",
                created=0,
            )
        ]
    return AgentListResponse(data=agents)
