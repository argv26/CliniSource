"""Unit tests for Pre-Step Clinical Planning Engine (AttendingPlanner) and Prompt Caching."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.orchestrator import AgentOrchestrator
from agent.planner import AttendingPlanner, ClinicalPlan
from agent.prompts import INVARIANT_SYSTEM_PROMPT, PLANNER_SYSTEM_INSTRUCTION, SYSTEM_PROMPT


def test_missing_api_key_raises_runtime_error(monkeypatch):
    """Planner must raise RuntimeError immediately if no LLM API key is configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = AttendingPlanner(api_key=None, openai_api_key=None)
    with pytest.raises(RuntimeError, match="LLM API key not configured for AttendingPlanner"):
        planner.plan("What are the causes of hypercalcemia?")


def test_parse_plan_json_markdown_fences():
    """Validates robust parsing of JSON wrapped in markdown code fences."""
    planner = AttendingPlanner(api_key="dummy-key")
    raw_fenced = """```json
    {
      "diagnostic_hypotheses": ["Primary Hyperparathyroidism", "Malignancy"],
      "organ_systems": ["Endocrine", "Skeletal System"],
      "search_queries": ["hypercalcemia PTH mediated causes", "PTHrP malignancy osteolytic lesions"],
      "evidence_checklist": ["Serum calcium > 10.5 mg/dL", "Intact PTH level elevated or inappropriately normal"]
    }
    ```"""
    plan = planner._parse_plan_json(raw_fenced, fallback_query="hypercalcemia")
    assert isinstance(plan, ClinicalPlan)
    assert len(plan.diagnostic_hypotheses) == 2
    assert "Primary Hyperparathyroidism" in plan.diagnostic_hypotheses
    assert "Endocrine" in plan.organ_systems
    assert len(plan.search_queries) == 2
    assert len(plan.evidence_checklist) == 2
    assert plan.to_dict()["diagnostic_hypotheses"] == plan.diagnostic_hypotheses


def test_parse_plan_json_fallback_query():
    """Validates that fallback query is populated if LLM returns empty search queries."""
    planner = AttendingPlanner(api_key="dummy-key")
    raw_empty = """{"diagnostic_hypotheses": ["Condition X"], "search_queries": []}"""
    plan = planner._parse_plan_json(raw_empty, fallback_query="Explain the brachial plexus")
    assert plan.search_queries == ["Explain the brachial plexus"]
    assert plan.diagnostic_hypotheses == ["Condition X"]


def test_planner_gemini_client_mock():
    """Validates that AttendingPlanner calls Gemini client and parses response."""
    planner = AttendingPlanner(api_key="test-api-key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "diagnostic_hypotheses": ["Pheochromocytoma"],
        "organ_systems": ["Adrenal Medulla"],
        "search_queries": ["pheochromocytoma catecholamine synthesis", "plasma metanephrines"],
        "evidence_checklist": ["Confirm biochemical catecholamine excess"],
    })
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        plan = planner.plan(
            user_message="What are the signs of pheochromocytoma?",
            active_books=["Williams_Endocrinology"],
        )

    assert plan.diagnostic_hypotheses == ["Pheochromocytoma"]
    assert plan.organ_systems == ["Adrenal Medulla"]
    assert len(plan.search_queries) == 2
    assert "pheochromocytoma catecholamine synthesis" in plan.search_queries


def test_orchestrator_stream_turn_emits_plan():
    """Validates that AgentOrchestrator.stream_turn emits 'event: plan' before tool retrieval."""
    mock_plan = ClinicalPlan(
        diagnostic_hypotheses=["Addison's Disease"],
        organ_systems=["Adrenal Cortex"],
        search_queries=["adrenal insufficiency cortisol aldosterone deficiency"],
        evidence_checklist=["Low morning cortisol", "High ACTH"],
    )
    mock_planner = MagicMock()
    mock_planner.plan.return_value = mock_plan

    orchestrator = AgentOrchestrator(planner=mock_planner)

    events = []
    for item in orchestrator.stream_turn(
        session_id="test_plan_stream_sess",
        user_message="What causes primary adrenal insufficiency?",
    ):
        events.append(item)

    event_names = [e.get("event") for e in events]
    assert "plan" in event_names, f"Expected 'plan' in events, got: {event_names}"

    # Plan must be emitted before tools, tokens, or citations
    plan_index = event_names.index("plan")
    assert plan_index > 0  # after initial status
    if "tools" in event_names:
        tools_index = event_names.index("tools")
        assert plan_index < tools_index, "event: plan must precede event: tools"
    if "token" in event_names:
        token_index = event_names.index("token")
        assert plan_index < token_index, "event: plan must precede event: token"

    plan_data = events[plan_index]["data"]
    assert plan_data["diagnostic_hypotheses"] == ["Addison's Disease"]
    assert plan_data["search_queries"] == ["adrenal insufficiency cortisol aldosterone deficiency"]


def test_prompt_caching_prefix_invariance():
    """Validates that INVARIANT_SYSTEM_PROMPT is deterministic and static."""
    assert INVARIANT_SYSTEM_PROMPT == SYSTEM_PROMPT
    assert "You are an expert Clinical Tutor" in INVARIANT_SYSTEM_PROMPT
    assert "[1]" in INVARIANT_SYSTEM_PROMPT  # citation contract
    assert "LaTeX" in INVARIANT_SYSTEM_PROMPT  # typography rule

    # Must be of substantial length (>1000 characters) to ensure prompt cache hit eligibility
    assert len(INVARIANT_SYSTEM_PROMPT) > 1500

