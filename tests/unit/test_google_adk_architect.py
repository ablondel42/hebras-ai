"""Unit tests for Google ADK n8n Workflow Architect Agent, tools, and episodic memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from google.adk.agents.llm_agent import Agent
from google.adk.labs.openai import OpenAILlm

from integrations.google_adk.agent import root_agent
from integrations.google_adk.memory.store import EpisodicMemoryStore
from integrations.google_adk.tools import workflow_proposer as wp
from integrations.google_adk.tools.local_templates import read_local_templates
from integrations.google_adk.tools.memory_tools import (
    recall_learned_patterns,
    record_learned_pattern,
)
from integrations.google_adk.tools.roi_evaluator import evaluate_workflow_roi_and_pain
from integrations.google_adk.tools.validator import validate_n8n_workflow
from integrations.google_adk.tools.web_search import search_web_workflows
from integrations.google_adk.tools.workflow_proposer import (
    _sanitize_slug,
    propose_and_save_workflow,
)


def test_episodic_memory_store_lifecycle(tmp_path: Path):
    """Test EpisodicMemoryStore initialization, recording, recall, and filtering."""
    store_file = tmp_path / "test_patterns.json"
    store = EpisodicMemoryStore(storage_path=store_file)

    # Initially populates default seed patterns
    initial = store.list_all()
    assert len(initial) >= 3

    # Record a new high-ROI pattern
    recorded = store.record(
        pattern_name="custom_dunning_flow",
        description="Automated Stripe payment failure recovery",
        topology_summary="Webhook -> Code -> Local LLM -> Slack",
        lessons_learned="Always authenticate webhooks and route LLM to port 8000.",
        customer_pain="High involuntary churn from expired cards.",
        monetization_potential="Recaptures $12,000/mo in subscription revenue.",
        roi_score=10,
        tags=["stripe", "churn", "saas"],
    )
    assert recorded["pattern_name"] == "custom_dunning_flow"
    assert recorded["roi_score"] == 10
    assert recorded["validation_status"] == "verified"

    # Recall by topic keyword
    matches = store.recall(query="dunning", limit=5)
    assert len(matches) >= 1
    assert any(m["pattern_name"] == "custom_dunning_flow" for m in matches)

    # Recall with minimum ROI score filter
    high_roi = store.recall(min_roi_score=10, limit=10)
    assert all(m["roi_score"] >= 10 for m in high_roi)

    # Empty query recalls latest sorted
    all_recalled = store.recall(limit=2)
    assert len(all_recalled) == 2


def test_memory_tools_wrappers():
    """Test memory_tools module functions."""
    rec = record_learned_pattern(
        pattern_name="test_memory_tool",
        description="Testing memory wrapper tool",
        topology_summary="Node A -> Node B",
        lessons_learned="Test lesson",
        customer_pain="Manual effort",
        monetization_potential="Cost savings",
        roi_score=8,
    )
    assert rec["pattern_name"] == "test_memory_tool"

    recalled = recall_learned_patterns(topic="test_memory_tool")
    assert len(recalled) >= 1
    assert recalled[0]["pattern_name"] == "test_memory_tool"


def test_web_search_tool_market_pain_and_roi():
    """Test search_web_workflows returns customer pain, monetization, and URLs."""
    results = search_web_workflows("leads", search_focus="market_pain_and_roi", max_results=3)
    assert len(results) >= 1

    first = results[0]
    assert "title" in first
    assert "url" in first
    assert "customer_pain" in first
    assert "monetization_potential" in first
    assert len(first["customer_pain"]) > 10
    assert len(first["monetization_potential"]) > 10

    # Fallback on generic query
    fallback_results = search_web_workflows("general", max_results=2)
    assert len(fallback_results) >= 1


def test_roi_evaluator_tool_scoring():
    """Test evaluate_workflow_roi_and_pain analyzes pain severity and monetization."""
    # Test high-pain revenue case
    res_rev = evaluate_workflow_roi_and_pain(
        "Automated Stripe failed payment recovery and involuntary churn reduction"
    )
    assert res_rev["overall_roi_score"] >= 8
    assert res_rev["customer_pain_intensity"] >= 7
    assert res_rev["customer_pain_severity"] in ["High", "Critical"]
    assert "Direct Top-Line Revenue" in res_rev["monetization_model"]
    assert "Subscription SaaS" in res_rev["target_audience"]

    # Test operational efficiency case
    res_eff = evaluate_workflow_roi_and_pain(
        "Automated AP invoice data extraction and ERP reconciliation"
    )
    assert res_eff["overall_roi_score"] >= 7
    assert "Labor Elimination" in res_eff["monetization_model"]
    assert "Accounting" in res_eff["target_audience"]


def test_local_templates_tool():
    """Test read_local_templates index and individual loading."""
    index = read_local_templates()
    assert index["status"] == "success"
    assert index["total_templates"] == 4

    template_names = [t["template_name"] for t in index["templates"]]
    assert "secure_webhook" in template_names
    assert "error_handler" in template_names
    assert "api_batch_polling" in template_names
    assert "ai_agent_chain" in template_names

    # Load specific template
    item = read_local_templates("secure_webhook")
    assert item["status"] == "success"
    assert item["template_name"] == "secure_webhook"
    assert item["node_count"] > 0
    assert "workflow" in item

    # Load missing template
    missing = read_local_templates("non_existent_template")
    assert missing["status"] == "error"
    assert "available_options" in missing


def test_validator_tool_closed_loop():
    """Test validate_n8n_workflow on valid, invalid schema, and security violations."""
    # Valid minimal workflow
    valid_wf: dict[str, Any] = {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {
                    "httpMethod": "POST",
                    "path": "test",
                    "authentication": "headerAuth",
                },
            },
            {
                "id": "2",
                "name": "Error Trigger",
                "type": "n8n-nodes-base.errorTrigger",
                "typeVersion": 1,
                "position": [100, 400],
                "parameters": {},
            },
        ],
        "connections": {},
        "pinData": {},
    }
    v_res = validate_n8n_workflow(valid_wf, strict=False)
    assert v_res["valid"] is True
    assert v_res["error_count"] == 0

    # Invalid JSON string
    v_bad_json = validate_n8n_workflow("{invalid json}")
    assert v_bad_json["valid"] is False
    assert v_bad_json["errors"][0]["rule_id"] == "SCH001"

    # Security violation (SEC001 plaintext secret)
    wf_secret = {
        "nodes": [
            {
                "id": "1",
                "name": "SecretNode",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {"apiKey": "sk-ant-api03-abcdefghijklmnop123456789"},
            }
        ],
        "connections": {},
    }
    v_secret = validate_n8n_workflow(wf_secret, strict=False)
    assert v_secret["valid"] is False
    assert any(e["rule_id"] == "SEC001" for e in v_secret["errors"])

    # LLM wrapper violation (LLM001 external host)
    wf_external_llm = {
        "nodes": [
            {
                "id": "1",
                "name": "OpenAI Chat",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {"options": {"baseURL": "https://api.openai.com/v1"}},
            }
        ],
        "connections": {},
    }
    v_llm = validate_n8n_workflow(wf_external_llm, strict=False)
    assert v_llm["valid"] is False
    assert any(e["rule_id"] == "LLM001" for e in v_llm["errors"])


def test_workflow_proposer_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test propose_and_save_workflow deterministic gate and persistence."""
    monkeypatch.setattr(wp, "WORKFLOWS_BASE_DIR", tmp_path / "workflows")

    invalid_wf = {
        "nodes": [
            {
                "id": "1",
                "name": "InsecureWebhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {"authentication": "none"},  # Violates SEC002
            }
        ],
        "connections": {},
    }

    # Should be rejected
    fail_res = propose_and_save_workflow(
        slug="insecure_webhook",
        workflow_json=invalid_wf,
        documentation_md="# Insecure Webhook",
    )
    assert fail_res["status"] == "error"
    assert "failed deterministic validation" in fail_res["message"]
    assert not (tmp_path / "workflows" / "insecure_webhook").exists()

    # Valid workflow should succeed
    valid_wf = {
        "name": "B2B Lead Qualification",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Receiver",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [100, 200],
                "parameters": {
                    "httpMethod": "POST",
                    "path": "leads",
                    "authentication": "headerAuth",
                },
            },
            {
                "id": "2",
                "name": "Local LLM Classifier",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1,
                "position": [300, 200],
                "parameters": {"options": {"baseURL": "http://localhost:8000/v1"}},
            },
            {
                "id": "3",
                "name": "Error Handler Trigger",
                "type": "n8n-nodes-base.errorTrigger",
                "typeVersion": 1,
                "position": [100, 400],
                "parameters": {},
            },
        ],
        "connections": {
            "Webhook Receiver": {
                "main": [[{"node": "Local LLM Classifier", "type": "main", "index": 0}]]
            }
        },
        "pinData": {},
    }

    roi_score = {
        "overall_roi_score": 9,
        "customer_pain_intensity": 9,
        "customer_pain_severity": "Critical",
        "monetization_model": "Sales Pipeline Acceleration",
        "estimated_monthly_financial_impact": "$10,000/mo",
        "estimated_hours_saved_monthly": "35 hours/mo",
        "target_audience": "B2B SaaS Revenue Teams",
        "implementation_complexity": "Medium",
        "pricing_recommendation": "$5,000 client deliverable",
        "executive_rationale": "Directly eliminates lead drop-off within 5 minutes.",
    }

    success_res = propose_and_save_workflow(
        slug="b2b_lead_qualification",
        workflow_json=valid_wf,
        documentation_md="# B2B Lead Qualification\n\nHigh speed lead triage.",
        roi_score=roi_score,
    )
    assert success_res["status"] == "success"
    target_dir = tmp_path / "workflows" / "b2b_lead_qualification"
    assert (target_dir / "workflow.json").exists()
    assert (target_dir / "README.md").exists()

    readme_content = (target_dir / "README.md").read_text()
    assert "## Business Value, Customer Pain & Monetization Analysis" in readme_content
    assert "Overall ROI Score" in readme_content
    assert "Sales Pipeline Acceleration" in readme_content


def test_sanitize_slug():
    """Test slug sanitization."""
    assert _sanitize_slug("B2B Lead Triage!!") == "b2b_lead_triage"
    assert _sanitize_slug("  Payment_Recovery--2026  ") == "payment_recovery--2026"


def test_root_agent_configuration():
    """Test root_agent instance properties, tools, and model configuration."""
    assert isinstance(root_agent, Agent)
    assert root_agent.name == "root_agent"
    assert isinstance(root_agent.model, OpenAILlm)
    assert root_agent.model.model == "Gemini 3.8 Flash"
    assert "8000" in str(root_agent.model.client.base_url)
    assert len(root_agent.tools) == 7

    # Verify tool names
    tool_names = [t.__name__ for t in root_agent.tools]
    assert "search_web_workflows" in tool_names
    assert "evaluate_workflow_roi_and_pain" in tool_names
    assert "read_local_templates" in tool_names
    assert "validate_n8n_workflow" in tool_names
    assert "propose_and_save_workflow" in tool_names
    assert "recall_learned_patterns" in tool_names
    assert "record_learned_pattern" in tool_names

    # Verify instruction emphasizes pain, monetization, and local LLM
    inst = root_agent.instruction
    assert "ACUTE CUSTOMER PAIN" in inst
    assert "MONETIZATION & ROI" in inst
    assert "LLM001" in inst
    assert "http://localhost:8000/v1" in inst
