"""Episodic memory tools for n8n architect agent.

Allows the agent to recall prior validated topologies, lessons learned, and monetization
metrics, as well as record newly discovered workflow patterns into memory.
"""

from __future__ import annotations

from typing import Any

from integrations.google_adk.memory.store import EpisodicMemoryStore


def recall_learned_patterns(
    topic: str | None = None, min_roi_score: int | None = None
) -> list[dict[str, Any]]:
    """Recall past validated workflow patterns, edge case lessons, and monetization insights.

    Args:
        topic: Search term or industry keyword (e.g. 'crm', 'leads', 'churn', 'billing', 'stripe').
               If None, retrieves the latest high-ROI patterns.
        min_roi_score: Optional minimum business ROI score threshold (1 to 10).

    Returns:
        List of matching verified workflow architectures, customer pain analyses,
        and operational lessons learned.
    """
    store = EpisodicMemoryStore()
    return store.recall(query=topic, min_roi_score=min_roi_score, limit=5)


def record_learned_pattern(
    pattern_name: str,
    description: str,
    topology_summary: str,
    lessons_learned: str,
    customer_pain: str | None = None,
    monetization_potential: str | None = None,
    roi_score: int | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Persist a newly learned workflow pattern, customer pain analysis, and monetization review.

    Args:
        pattern_name: Unique slug or name for the pattern (e.g., 'chargeback_rebuttal_engine').
        description: High-level overview of what the workflow accomplishes.
        topology_summary: Summary of node connections and key components.
        lessons_learned: Architectural gotchas, security configurations, or local LLM prompt tips.
        customer_pain: The specific business or operational pain addressed.
        monetization_potential: Revenue impact, cost savings, or client pricing model.
        roi_score: Estimated business value score from 1 to 10.
        tags: Optional list of keyword tags.

    Returns:
        Confirmation dictionary containing the stored memory entry.
    """
    store = EpisodicMemoryStore()
    return store.record(
        pattern_name=pattern_name,
        description=description,
        topology_summary=topology_summary,
        lessons_learned=lessons_learned,
        customer_pain=customer_pain,
        monetization_potential=monetization_potential,
        roi_score=roi_score,
        tags=tags,
    )
