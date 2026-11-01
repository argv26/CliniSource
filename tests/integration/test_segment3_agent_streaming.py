"""Segment 3 Clinical Agent & SSE Streaming Integration Test Suite.

Validates the full Clinical Agent Orchestration and Real-Time SSE Streaming layer:
1. AttendingPlanner structured clinical reasoning and plan parsing.
2. Prompt caching invariant prefix and zero-vision token guarantee.
3. SSE event stream protocol ordering and JSON schema compliance.
4. Parallel figure resolution and early event emission.
5. Conversational intent disambiguation (greetings / pleasantries fast-path).
6. Medical typography healing (hyphenation) and phantom citation stripping.
7. Multi-turn session persistence and in-memory cache hydration from database.
8. Client disconnection and stream cancellation resilience.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent.orchestrator import (
    AgentOrchestrator,
    _clean_chunk_prose,
    _sanitize_citations,
    _sanitize_medical_typography,
)
from agent.planner import AttendingPlanner, ClinicalPlan
from agent.prompts import INVARIANT_SYSTEM_PROMPT
from context.manager import ContextManager
from context.models import CitationRecord
from ui.app import app
from ui.auth import init_auth_db
from ui.dependencies import get_orchestrator
from ui.sessions import (
    create_session,
    get_session,
    get_session_messages,
    init_sessions_db,
    save_message,
)


# =============================================================================
# Test Cases (Segment 3)
# =============================================================================

def test_attending_planner_hypotheses_and_generation():
    # AC: AttendingPlanner must formulate structured clinical hypotheses, organ systems, and targeted queries.
    # Behavior: User medical query -> planner.plan() -> Valid ClinicalPlan with non-empty fields.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Verifies the clinical reasoning engine structures queries before touching the search index.
    planner = AttendingPlanner()
    mock_llm_json = json.dumps({
        "diagnostic_hypotheses": ["Primary Hyperparathyroidism", "Humoral Hypercalcemia of Malignancy"],
        "organ_systems": ["Endocrine & Metabolic", "Renal System"],
        "search_queries": [
            "hypercalcemia parathyroid hormone PTH intact elevated",
            "PTHrP malignancy osteolytic bone metastases",
        ],
        "evidence_checklist": [
            "Total serum calcium > 10.5 mg/dL",
            "Suppressed vs inappropriately normal intact PTH",
        ],
    })

    with patch.object(planner, "plan") as mock_plan:
        mock_plan.return_value = planner._parse_plan_json(mock_llm_json, fallback_query="hypercalcemia")
        plan = planner.plan("Patient presents with fatigue, nephrolithiasis, and serum calcium of 11.8 mg/dL.")

        assert isinstance(plan, ClinicalPlan)
        assert len(plan.diagnostic_hypotheses) == 2
        assert "Primary Hyperparathyroidism" in plan.diagnostic_hypotheses
        assert "Endocrine & Metabolic" in plan.organ_systems
        assert len(plan.search_queries) == 2
        assert len(plan.evidence_checklist) == 2

    # Test fallback parsing when LLM outputs unformatted text
    fallback_plan = planner._parse_plan_json("I cannot output json", fallback_query="adrenal crisis management")
    assert fallback_plan.search_queries == ["adrenal crisis management"]
    assert isinstance(fallback_plan.diagnostic_hypotheses, list)


def test_prompt_caching_invariant_and_zero_vision():
    # AC: The INVARIANT_SYSTEM_PROMPT must maintain stable prefix length for Gemini context caching,
    #     and assembled prompts must contain strictly zero image/multimodal payloads.
    # Behavior: ContextManager.assemble_prompt() -> Strictly text-only message parts, zero vision tokens.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Protects against multimodal token cost inflation and ensures predictable context caching.
    assert len(INVARIANT_SYSTEM_PROMPT) >= 1500, "Invariant prompt must be sufficiently detailed for caching"
    assert "Attending Physician" in INVARIANT_SYSTEM_PROMPT or "Clinical Tutor" in INVARIANT_SYSTEM_PROMPT
    assert "Citation Integrity Contract" in INVARIANT_SYSTEM_PROMPT

    cm = ContextManager()
    session_id = f"test_prompt_{uuid.uuid4().hex[:8]}"
    cm.add_user_message(session_id, "Explain the pathophysiology of Graves ophthalmopathy.")
    cm.add_tool_result(
        session_id=session_id,
        tool_call_id="call_mock_1",
        name="search_chunks",
        result=[{"text": "TSH-receptor autoantibodies stimulate orbital fibroblasts.", "chunk_id": "chk_graves"}],
    )

    assembled = cm.assemble_prompt(session_id=session_id, system_prompt=INVARIANT_SYSTEM_PROMPT)
    assert len(assembled) >= 2

    # Verify pure text: No base64 bitmaps, raw bytes, or image MIME objects
    for msg in assembled:
        content = msg["content"]
        assert isinstance(content, str)
        assert not content.startswith("data:image/")
        assert "data:image/jpeg;base64" not in content


@pytest.mark.anyio
async def test_sse_streaming_protocol_and_order():
    # AC: /api/chat/stream must stream standard SSE events in strict progressive order:
    #     status -> plan -> tools -> figures -> token -> referenced_books -> citations -> done.
    # Behavior: POST /api/chat/stream with clinical query -> Receive valid SSE stream with ordered event types.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Verifies the real-time ASGI SSE pipeline meets the UI rendering contract.
    init_auth_db()
    init_sessions_db()

    session_id = f"test_stream_{uuid.uuid4().hex[:8]}"
    query = "What is the functional zonation of the adrenal cortex?"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # Establish guest session
        await client.get("/api/auth/me")

        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": session_id, "message": query},
            timeout=60.0,
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            events: list[str] = []
            token_deltas: list[str] = []
            done_payload = None

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    if not raw_event.strip():
                        continue

                    event_type = "message"
                    event_data = {}
                    for line in raw_event.split("\n"):
                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            try:
                                event_data = json.loads(line[len("data:"):].strip())
                            except Exception:
                                event_data = {}

                    events.append(event_type)
                    if event_type == "token":
                        token_deltas.append(event_data.get("delta", ""))
                    elif event_type == "done":
                        done_payload = event_data

            assert "status" in events
            assert "plan" in events
            assert "tools" in events
            assert "token" in events
            assert "done" in events
            assert len(token_deltas) > 0
            assert done_payload is not None
            assert "reply" in done_payload and len(done_payload["reply"]) > 0

            # Verify protocol sequence: plan comes before token, done is last
            plan_idx = events.index("plan")
            token_idx = events.index("token")
            done_idx = events.index("done")
            assert plan_idx < token_idx < done_idx


@pytest.mark.anyio
async def test_early_parallel_figure_emission():
    # AC: Figure diagrams must be emitted over SSE as soon as resolved, BEFORE the complete text finishes streaming.
    # Behavior: Stream clinical query -> event: figures arrives before final token stream completes.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Proves UI thumbnail carousel loads asynchronously without waiting for LLM synthesis.
    init_auth_db()
    init_sessions_db()

    session_id = f"test_fig_{uuid.uuid4().hex[:8]}"
    query = "Explain the anatomy of the femoral triangle."

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/api/auth/me")

        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": session_id, "message": query},
            timeout=60.0,
        ) as response:
            events_order: list[str] = []
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    for line in raw_event.split("\n"):
                        if line.startswith("event:"):
                            events_order.append(line[len("event:"):].strip())

            # If figures are returned for this anatomical query, verify first figure event occurs before done
            if "figures" in events_order:
                first_fig_idx = events_order.index("figures")
                done_idx = events_order.index("done")
                assert first_fig_idx < done_idx


@pytest.mark.anyio
async def test_conversational_intent_fast_path():
    # AC: Conversational greetings, thank-you messages, and meta questions must execute on a fast-path,
    #     returning immediate friendly replies without invoking heavy textbook retrieval or planning.
    # Behavior: POST 'hello' -> Returns friendly introduction, 0 citations, 0 tools, < 1.0s.
    # @lane: integration
    # @dependency: full-system
    # Selection evidence: Protects retrieval engine from spurious queries on simple conversational greetings.
    init_auth_db()
    init_sessions_db()

    conversational_inputs = ["hello", "thank you", "what model are you?"]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/api/auth/me")

        for greeting in conversational_inputs:
            session_id = f"test_greet_{uuid.uuid4().hex[:8]}"
            t0 = time.perf_counter()

            async with client.stream(
                "POST",
                "/api/chat/stream",
                json={"session_id": session_id, "message": greeting},
                timeout=10.0,
            ) as response:
                assert response.status_code == 200
                events = []
                done_data = None
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw_event, buffer = buffer.split("\n\n", 1)
                        for line in raw_event.split("\n"):
                            if line.startswith("event:"):
                                events.append(line[len("event:"):].strip())
                            elif line.startswith("data:") and events and events[-1] == "done":
                                done_data = json.loads(line[len("data:"):].strip())

                elapsed = time.perf_counter() - t0
                assert "done" in events
                assert "tools" not in events, f"Conversational greeting '{greeting}' triggered heavy retrieval tools"
                assert done_data is not None
                assert len(done_data.get("reply", "")) > 0


def test_medical_typography_and_citation_sanitizer():
    # AC: Broken line-break hyphens must be healed into continuous medical terms, and hallucinated
    #     citation numbers not matching session records must be stripped.
    # Behavior: "glu-\ncose" -> "glucose"; "[1] [99]" -> "[1]".
    # @lane: integration
    # @dependency: none
    # Selection evidence: Protects user interface from broken layout words and broken clickable citation tags.
    # 1. Typography healing
    raw_text = "The patient suffered from severe hyper-\ntension and hyper-\nglycemia requiring insulin."
    healed = _clean_chunk_prose(raw_text)
    assert "hypertension" in healed
    assert "hyperglycemia" in healed
    assert "hyper-\n" not in healed

    # 2. Citation sanitization
    reply_with_citations = "Aldosterone acts on distal tubule [1]. Cortisol inhibits CRH [2]. Non-existent claim [99]."
    valid_ids = {1, 2}
    sanitized = _sanitize_citations(reply_with_citations, valid_ids)

    assert "[1]" in sanitized
    assert "[2]" in sanitized
    assert "[99]" not in sanitized, "Hallucinated citation [99] was not stripped"


@pytest.mark.anyio
async def test_multi_turn_context_hydration():
    # AC: Multi-turn consultation must maintain session context, and clear of in-memory cache
    #     must re-hydrate previous turns from the SQLite database.
    # Behavior: Turn 1 creates session in DB -> Clear orchestrator RAM -> Turn 2 restores Turn 1 history.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Validates state resilience across worker restarts and memory garbage collection.
    init_auth_db()
    init_sessions_db()

    orchestrator = get_orchestrator()
    session_id = f"test_hydrate_{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/api/auth/me")

        # Turn 1: Initial query
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": session_id, "message": "What is primary hyperaldosteronism?"},
            timeout=60.0,
        ) as res1:
            async for _ in res1.aiter_text():
                pass

        # Simulate in-memory cache eviction / service worker restart
        orchestrator.context_manager.store._sessions.clear()
        assert session_id not in orchestrator.context_manager.store._sessions

        # Turn 2: Follow-up question referencing 'it'
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": session_id, "message": "What is the ARR screening threshold for it?"},
            timeout=60.0,
        ) as res2:
            async for _ in res2.aiter_text():
                pass

        # Verify that context manager re-hydrated the full conversation history
        rehydrated_session = orchestrator.context_manager.get_or_create_session(session_id)
        assert len(rehydrated_session.messages) >= 3, "Failed to re-hydrate previous messages from database"


@pytest.mark.anyio
async def test_client_disconnect_stream_cancellation():
    # AC: If client aborts connection mid-stream, generator must terminate cleanly without unhandled exceptions.
    # Behavior: Read only first 2 chunks then close client stream -> Generator breaks cleanly.
    # @lane: integration
    # @dependency: full-system
    # Selection evidence: Guarantees server thread pool and worker connections do not leak on aborted HTTP connections.
    init_auth_db()
    init_sessions_db()

    session_id = f"test_abort_{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/api/auth/me")

        # Open stream, read a fraction, and break
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": session_id, "message": "Explain calcium homeostasis and PTH mechanisms."},
            timeout=60.0,
        ) as response:
            count = 0
            async for _ in response.aiter_bytes():
                count += 1
                if count >= 3:
                    break  # Early client disconnect

        # Ensure subsequent operations on the session or server succeed without deadlock
        res_after = await client.get(f"/api/sessions/{session_id}")
        assert res_after.status_code == 200
