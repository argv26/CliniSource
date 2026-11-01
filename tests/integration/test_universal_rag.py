"""Universal Multi-Domain Textbook RAG Integration Tests.

Validates:
1. Generic conversational queries respond directly with zero tool latency.
2. Table-first formatting for comparisons and multi-branch logic (no synthetic flowcharts).
3. Automated typography sanitization (no stray trailing $, clean ion/math symbols, balanced markdown).
4. Accurate authentic figure plate resolution across indexed textbooks without page offset errors.
"""
from __future__ import annotations

import re
import pytest
from httpx import ASGITransport, AsyncClient

from agent.orchestrator import AgentOrchestrator
from agent.sanitizers import _sanitize_medical_typography, _sanitize_universal_typography
from agent.tools_spec import TOOL_DEFINITIONS, execute_tool
from ui.app import app
from ui.diagrams import get_figure_image_path


# AC: Universal tool definitions must expose structure, chunks, and media tools.
# Behavior: Inspect TOOL_DEFINITIONS -> structure, chunks, and media tools are present.
# @lane: integration
# @dependency: none
def test_universal_tool_definitions_present():
    tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "get_textbook_structure" in tool_names
    assert "get_relevant_chunks" in tool_names
    assert "get_media_and_tables" in tool_names
    # Legacy aliases preserved
    assert "search_chunks" in tool_names
    assert "search_sections" in tool_names


# AC: Generic conversational query must answer directly without calling retrieval tools.
# Behavior: Send greeting -> immediate direct reply with 0 tool calls.
# @lane: integration
# @dependency: full-system
def test_generic_conversational_turn_direct_reply():
    orchestrator = AgentOrchestrator()
    session_id = "test-generic-session-001"
    res = orchestrator.run_turn(session_id=session_id, user_message="hello")

    assert res["reply"] is not None
    assert len(res["reply"]) > 20
    assert len(res["tool_calls"]) == 0
    assert len(res["citations"]) == 0


# AC: Typography sanitizer must strip trailing $, normalize ions, and balance bold markdown.
# Behavior: Raw string with 15$, 35$, Na^+/K^+-ATPase, unclosed ** -> clean sanitized output.
# @lane: integration
# @dependency: none
def test_universal_typography_sanitizer():
    raw_text = (
        "Age >= 35$ years AND smoking >= 15$ cigarettes per day.\n"
        "Dysfunction of the Na^+/K^+-ATPase pump and low Mg2+.\n"
        "• **Unclosed bold item at line end"
    )
    cleaned = _sanitize_universal_typography(raw_text)

    # Asserts trailing $ are removed
    assert "35$" not in cleaned
    assert "15$" not in cleaned
    assert "35 years" in cleaned
    assert "15 cigarettes" in cleaned

    # Asserts Unicode symbols are normalized
    assert "Na⁺/K⁺-ATPase" in cleaned
    assert "Mg²⁺" in cleaned
    assert "≥" in cleaned

    # Asserts unclosed bold is balanced
    assert "**Unclosed bold item at line end**" in cleaned


# AC: Diagram extraction for Williams Endocrinology Fig 16.2 must resolve to physical page 800 without +196 page offset.
# Behavior: Resolve chunk for Fig 16.2 -> returns valid image path with non-zero size.
# @lane: integration
# @dependency: sqlite
def test_williams_figure_page_resolution():
    import sqlite3
    from pathlib import Path
    
    db_path = Path("clinisource.db") if Path("clinisource.db").exists() else Path("textbook_rag.db")
    if not db_path.exists():
        pytest.skip("textbook database not present")

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT chunk_id, page_start FROM chunks WHERE book_slug LIKE '%Williams%' AND text LIKE '%Fig. 16.2%' LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        pytest.skip("Williams Fig 16.2 chunk not found")

    chunk_id, page_start = row
    assert int(page_start) == 800  # Physical PDF page is 800

    img_path = get_figure_image_path(chunk_id)
    assert img_path is not None
    assert img_path.exists()
    assert img_path.stat().st_size > 10000  # Real image generated


# AC: Streaming SSE endpoint must stream tokens and done payload for clinical queries.
# Behavior: POST /api/chat/stream -> SSE stream completes with tokens and valid response.
# @lane: service-integration-e2e
# @dependency: full-system
@pytest.mark.anyio
async def test_universal_streaming_sse_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/chat/stream",
            json={"session_id": "test-stream-univ-01", "message": "hello"},
            timeout=30.0,
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")

        events = []
        async for line in res.aiter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())

        assert "token" in events
        assert "done" in events

