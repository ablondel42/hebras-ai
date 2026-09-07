"""Episodic memory store for n8n workflow architect agent.

Persists validated topologies, customer pain analyses, monetization insights,
and operational lessons learned to enable continuous self-improvement across turns.
"""

from __future__ import annotations

import datetime
import json
import time
import uuid
from pathlib import Path
from typing import Any

from integrations.google_adk.logging import format_adk_tree, get_adk_logger

logger = get_adk_logger("memory.store")

DEFAULT_MEMORY_FILE = Path(__file__).parent / "episodic_patterns.json"

DEFAULT_SEED_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "pattern-seed-lead-triage",
        "pattern_name": "b2b_lead_triage_enrichment",
        "description": "High-velocity B2B lead capture, enrichment, and automated scoring.",
        "topology_summary": "Webhook (headerAuth) -> Schema Validation -> Local LLM (Gemini 3.8 Flash @ :8000) ICP Classification -> CRM Update -> Alerting",
        "customer_pain": "Slow sales lead qualification response times leading to 40%+ drop-off in conversion and high manual rep overhead.",
        "monetization_potential": "Drives immediate top-line pipeline expansion; billable agency automation valued at $3,500-$6,000 setup.",
        "roi_score": 9,
        "lessons_learned": "Enforce SEC002 authentication on incoming webhooks. Strictly route all LLM operations through http://localhost:8000/v1 (LLM001). Ensure CRM nodes handle batch rate limits.",
        "tags": ["b2b", "sales", "crm", "lead_scoring", "revenue_growth"],
        "created_at": "2026-09-06T20:00:00Z",
        "validation_status": "verified",
    },
    {
        "id": "pattern-seed-dunning-recovery",
        "pattern_name": "payment_failure_dunning_recovery",
        "description": "Automated SaaS churn prevention and payment failure recovery workflow.",
        "topology_summary": "Payment Webhook (headerAuth) -> Account Lookup -> Local LLM Personalized Recovery Strategy -> Multi-tier Dunning Dispatch -> Audit Logging",
        "customer_pain": "Involuntary churn due to failed recurring payments causing 5-10% monthly revenue erosion in subscription businesses.",
        "monetization_potential": "Direct revenue preservation; instantly recaptures $10,000-$50,000 monthly ARR with demonstrable ROI.",
        "roi_score": 10,
        "lessons_learned": "Never include raw gateway API keys in workflow definitions (SEC001). Leverage local LLM (LLM001) for personalized customer outreach copy.",
        "tags": ["fintech", "churn_recovery", "stripe", "dunning", "revenue_retention"],
        "created_at": "2026-09-06T20:00:00Z",
        "validation_status": "verified",
    },
    {
        "id": "pattern-seed-billing-reconciliation",
        "pattern_name": "automated_billing_reconciliation",
        "description": "Cross-platform transaction reconciliation and accounting variance detection.",
        "topology_summary": "Schedule Trigger -> SplitInBatches (batchSize: 50) -> Gateway & ERP Fetch -> Code Discrepancy Matcher -> Local LLM Explainer -> Anomaly Alert & Error Trigger",
        "customer_pain": "Manual reconciliation of thousands of payment records eating 25+ finance hours monthly with error-prone spreadsheet audits.",
        "monetization_potential": "Saves $3,000+/month in manual bookkeeping costs and eliminates financial audit penalties.",
        "roi_score": 8,
        "lessons_learned": "Mandate SplitInBatches to comply with LEAN001. Connect an explicit Error Trigger node (LEAN002) for audit discrepancy alerting.",
        "tags": ["accounting", "reconciliation", "batch_processing", "cost_reduction"],
        "created_at": "2026-09-06T20:00:00Z",
        "validation_status": "verified",
    },
]


class EpisodicMemoryStore:
    """Manages persistent episodic memory for n8n workflow architecture."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else DEFAULT_MEMORY_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure storage directory and JSON file exist with seed data."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._save_patterns(DEFAULT_SEED_PATTERNS)
            logger.info(
                format_adk_tree(
                    f"Initialized episodic store with seed patterns at {self.storage_path.name}",
                    [
                        ("Seed Patterns", len(DEFAULT_SEED_PATTERNS)),
                        ("Storage Path", str(self.storage_path)),
                    ],
                )
            )

    def _load_patterns(self) -> list[dict[str, Any]]:
        """Load patterns from disk."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []

    def _save_patterns(self, patterns: list[dict[str, Any]]) -> None:
        """Atomically persist patterns to disk."""
        temp_file = self.storage_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.storage_path)
        logger.debug(f"Persisted {len(patterns)} pattern(s) to {self.storage_path.name}")

    def recall(
        self,
        query: str | None = None,
        min_roi_score: int | float | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search and recall past validated patterns from episodic memory.

        Args:
            query: Keyword query to match against pattern fields (name, description,
                   customer pain, monetization potential, lessons learned, tags).
            min_roi_score: Minimum ROI score filter (1-10).
            limit: Maximum number of patterns to return.

        Returns:
            List of matching pattern dictionaries sorted by score and recency.
        """
        start_time = time.perf_counter()
        patterns = self._load_patterns()
        results: list[dict[str, Any]] = []

        query_terms = [t.lower() for t in query.split()] if query else []

        for item in patterns:
            score = item.get("roi_score", 0)
            if min_roi_score is not None and score < min_roi_score:
                continue

            if not query_terms:
                results.append(item)
                continue

            searchable_text = " ".join(
                [
                    str(item.get("pattern_name", "")),
                    str(item.get("description", "")),
                    str(item.get("topology_summary", "")),
                    str(item.get("customer_pain", "")),
                    str(item.get("monetization_potential", "")),
                    str(item.get("lessons_learned", "")),
                    " ".join(item.get("tags", [])),
                ]
            ).lower()

            # Check if any search term matches
            match_count = sum(1 for term in query_terms if term in searchable_text)
            if match_count > 0:
                results.append(item)

        # Sort by ROI score descending, then created_at descending
        results.sort(
            key=lambda x: (x.get("roi_score", 0), x.get("created_at", "")),
            reverse=True,
        )
        returned = results[:limit]
        elapsed = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            format_adk_tree(
                f"Episodic memory search matched {len(returned)} pattern(s)",
                [
                    ("Query", query or "None"),
                    ("Min ROI Filter", min_roi_score or "None"),
                    ("Store Total", len(patterns)),
                    ("Matches", [r.get("pattern_name") for r in returned]),
                ],
                duration_ms=elapsed,
            )
        )
        return returned

    def record(
        self,
        pattern_name: str,
        description: str,
        topology_summary: str,
        lessons_learned: str,
        customer_pain: str | None = None,
        monetization_potential: str | None = None,
        roi_score: int | float | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record a newly validated workflow pattern and business evaluation into memory.

        Args:
            pattern_name: Machine/slug name for the pattern.
            description: Concise summary of what the workflow does.
            topology_summary: Core node sequence and data flow.
            lessons_learned: Remediation lessons, edge cases, and architectural best practices.
            customer_pain: Specific customer pain point resolved by this workflow.
            monetization_potential: Commercial viability, pricing model, or ROI projection.
            roi_score: Business value score from 1 to 10.
            tags: Optional categorisation tags.

        Returns:
            The recorded pattern dictionary.
        """
        start_time = time.perf_counter()
        patterns = self._load_patterns()
        entry: dict[str, Any] = {
            "id": f"pattern-{uuid.uuid4().hex[:10]}",
            "pattern_name": pattern_name,
            "description": description,
            "topology_summary": topology_summary,
            "customer_pain": customer_pain or "Not specified",
            "monetization_potential": monetization_potential or "Not specified",
            "roi_score": int(roi_score) if roi_score is not None else 7,
            "lessons_learned": lessons_learned,
            "tags": tags or [],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "validation_status": "verified",
        }
        patterns.append(entry)
        self._save_patterns(patterns)
        elapsed = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            format_adk_tree(
                f"Episodic memory saved new pattern '{pattern_name}'",
                [
                    ("Entry ID", entry["id"]),
                    ("Pattern Name", pattern_name),
                    ("ROI Score", entry["roi_score"]),
                    ("Total Patterns in Store", len(patterns)),
                ],
                duration_ms=elapsed,
            )
        )
        return entry

    def list_all(self) -> list[dict[str, Any]]:
        """Return all patterns in memory."""
        return self._load_patterns()

    def clear(self) -> None:
        """Clear memory patterns (useful for tests)."""
        self._save_patterns([])
        logger.debug("Episodic memory store cleared.")
