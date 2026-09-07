"""ROI and Customer Pain evaluation tool for n8n workflow architect agent.

Provides objective business case analysis, customer pain intensity scoring,
and commercial monetization potential for proposed automations.
"""

from __future__ import annotations

import re
from typing import Any

# Domain indicator keywords for automatic heuristic scoring
REVENUE_INDICATORS = {
    "churn", "dunning", "payment", "revenue", "sales", "lead", "pipeline",
    "stripe", "subscription", "chargeback", "dispute", "pricing", "checkout"
}

EFFICIENCY_INDICATORS = {
    "invoice", "reconciliation", "accounting", "support", "ticket", "erp",
    "manual", "scraping", "enrichment", "triage", "compliance", "audit"
}

HIGH_PAIN_INDICATORS = {
    "churn", "lost", "fail", "slow", "delay", "error", "penalty", "dispute",
    "overdue", "leakage", "friction", "bottleneck", "rejection", "unpaid"
}


def evaluate_workflow_roi_and_pain(
    workflow_summary: str, target_audience: str | None = None
) -> dict[str, Any]:
    """Evaluate an n8n workflow concept across customer pain severity and monetization potential.

    Args:
        workflow_summary: Summary of the workflow problem, proposed solution, and topology.
        target_audience: Optional target customer segment (e.g., 'B2B SaaS', 'E-Commerce', 'Agencies').

    Returns:
        Structured evaluation containing customer pain intensity (1-10), monetization
        potential (1-10), estimated financial savings, and strategic implementation guidance.
    """
    summary_lower = workflow_summary.lower()
    words = set(re.findall(r"\b\w+\b", summary_lower))

    # Calculate pain score heuristic (baseline: 7)
    pain_matches = len(words.intersection(HIGH_PAIN_INDICATORS))
    pain_score = min(10, max(5, 7 + pain_matches))

    # Calculate monetization / revenue impact heuristic
    revenue_matches = len(words.intersection(REVENUE_INDICATORS))
    efficiency_matches = len(words.intersection(EFFICIENCY_INDICATORS))
    
    if revenue_matches > 1:
        monetization_score = min(10, 8 + revenue_matches)
        monetization_model = "Direct Top-Line Revenue Acceleration & Churn Recapture"
        estimated_monthly_value = "$5,000 - $25,000 / month in preserved or accelerated revenue"
        pricing_rec = "Package as premium agency offer ($4,000-$7,500 setup) or monthly revenue share"
    elif efficiency_matches > 0:
        monetization_score = min(9, 7 + efficiency_matches)
        monetization_model = "Operational Labor Elimination & Error Prevention"
        estimated_monthly_value = "$2,000 - $6,000 / month in reduced manual labor hours"
        pricing_rec = "Package as operational retainer ($2,500 setup + $500/mo maintenance)"
    else:
        monetization_score = 7
        monetization_model = "Process Automation & Data Synchronization"
        estimated_monthly_value = "$1,000 - $3,000 / month in workflow efficiency"
        pricing_rec = "Standard fixed-price implementation ($1,500-$3,000)"

    overall_roi_score = round((pain_score * 0.45) + (monetization_score * 0.55))

    detected_audience = target_audience
    if not detected_audience:
        if "lead" in summary_lower or "sales" in summary_lower or "crm" in summary_lower:
            detected_audience = "B2B Sales & Revenue Operations Teams"
        elif "stripe" in summary_lower or "churn" in summary_lower or "subscription" in summary_lower:
            detected_audience = "Subscription SaaS Founders & Finance Leaders"
        elif "invoice" in summary_lower or "reconciliation" in summary_lower or "accounting" in summary_lower:
            detected_audience = "Corporate Finance & Accounting Departments"
        elif "support" in summary_lower or "ticket" in summary_lower:
            detected_audience = "Customer Success & Support Operations"
        else:
            detected_audience = "Digital Agencies & High-Growth SMBs"

    complexity = "Medium"
    if "agent" in summary_lower or "reconciliation" in summary_lower or "dispute" in summary_lower:
        complexity = "Medium-High"
    elif "webhook" in summary_lower and "alert" in summary_lower:
        complexity = "Low-Medium"

    return {
        "overall_roi_score": overall_roi_score,
        "customer_pain_intensity": pain_score,
        "customer_pain_severity": "Critical" if pain_score >= 9 else "High",
        "monetization_potential": monetization_score,
        "monetization_model": monetization_model,
        "estimated_monthly_financial_impact": estimated_monthly_value,
        "estimated_hours_saved_monthly": "20 - 45 hours/month",
        "target_audience": detected_audience,
        "implementation_complexity": complexity,
        "pricing_recommendation": pricing_rec,
        "executive_rationale": (
            f"This automation directly targets high-severity pain in {detected_audience}. "
            f"With an overall ROI score of {overall_roi_score}/10, it yields demonstrable financial return "
            f"via {monetization_model.lower()}."
        ),
    }
