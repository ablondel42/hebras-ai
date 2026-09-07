"""Local templates retrieval tool for n8n workflow architect agent.

Provides access to vetted canonical seed blueprints in knowledge/n8n/templates/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from integrations.google_adk.logging import format_adk_tree, get_adk_logger

logger = get_adk_logger("tools.local_templates")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "n8n" / "templates"

TEMPLATE_METADATA: dict[str, dict[str, str]] = {
    "secure_webhook": {
        "description": "Production webhook receiver enforcing SEC002 authentication and input validation.",
        "best_for": "Incoming API triggers, CRM webhook ingestion, Stripe notifications, form submissions.",
    },
    "error_handler": {
        "description": "Global error handler triggered by n8n-nodes-base.errorTrigger dispatching alerts.",
        "best_for": "Mission-critical reliability, Slack/incident alerting, and LEAN002 compliance.",
    },
    "api_batch_polling": {
        "description": "Scheduled API polling workflow using splitInBatches for rate-limit protection.",
        "best_for": "Bulk data synchronization, ERP/CRM reconciliation, and LEAN001 compliance.",
    },
    "ai_agent_chain": {
        "description": "LangChain conversational agent routing to local model on port 8000 (LLM001).",
        "best_for": "Contextual classification, customer reply generation, and automated intent parsing.",
    },
}


def read_local_templates(template_name: str | None = None) -> dict[str, Any]:
    """Read canonical production n8n seed templates from the local knowledge base.

    Args:
        template_name: Optional name of the template (e.g., 'secure_webhook', 'ai_agent_chain',
                       'api_batch_polling', 'error_handler'). If None, returns index of all templates.

    Returns:
        Index of available templates or the parsed workflow JSON definition of the requested template.
    """
    if not TEMPLATES_DIR.exists():
        logger.warning(f"Templates directory not found: {TEMPLATES_DIR}")
        return {
            "status": "error",
            "message": f"Templates directory not found at {TEMPLATES_DIR}",
            "available_templates": [],
        }

    available_files = {p.stem: p for p in TEMPLATES_DIR.glob("*.json")}

    if template_name is None:
        templates_index: list[dict[str, Any]] = []
        for stem, path in available_files.items():
            meta = TEMPLATE_METADATA.get(stem, {})
            templates_index.append(
                {
                    "template_name": stem,
                    "filename": path.name,
                    "description": meta.get("description", "Production n8n template"),
                    "best_for": meta.get("best_for", "Workflow automation"),
                }
            )
        logger.info(
            format_adk_tree(
                "Local templates catalog indexed",
                [
                    ("Total Templates", len(templates_index)),
                    ("Available Blueprints", list(available_files.keys())),
                ],
            )
        )
        return {
            "status": "success",
            "total_templates": len(templates_index),
            "templates": templates_index,
        }

    clean_name = template_name.replace(".json", "").strip().lower()
    target_path = available_files.get(clean_name)

    if not target_path or not target_path.exists():
        logger.warning(
            f"Template '{template_name}' not found. Available options: {list(available_files.keys())}"
        )
        return {
            "status": "error",
            "message": f"Template '{template_name}' not found.",
            "available_options": list(available_files.keys()),
        }

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        node_names = [n.get("name", "Unnamed") for n in workflow_data.get("nodes", [])]
        logger.info(
            format_adk_tree(
                f"Loaded seed template '{clean_name}'",
                [
                    ("Filename", target_path.name),
                    ("Node Count", len(node_names)),
                    ("Nodes", node_names[:5]),
                ],
            )
        )
        return {
            "status": "success",
            "template_name": clean_name,
            "filename": target_path.name,
            "description": TEMPLATE_METADATA.get(clean_name, {}).get("description", ""),
            "node_count": len(node_names),
            "nodes": node_names,
            "workflow": workflow_data,
        }
    except Exception as e:
        logger.error(f"Failed to parse template '{template_name}': {e}")
        return {
            "status": "error",
            "message": f"Failed to parse template '{template_name}': {e}",
        }
