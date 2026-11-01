"""Unit tests for SemanticBookRouter and Explicit UI Book Attribution."""
from __future__ import annotations

from unittest.mock import MagicMock

from agent.orchestrator import AgentOrchestrator
from agent.planner import ClinicalPlan
from context.models import CitationRecord
from retrieval.router import SemanticBookRouter, extract_referenced_books


def test_explicit_user_selection_preserved():
    """Explicit user selection of specific textbooks must be 100% preserved and never overridden."""
    router = SemanticBookRouter()
    # User chose only Anatomy, but asks an endocrine question
    routed = router.route(
        query="What are the mechanisms of thyroid hormone synthesis and TSH regulation?",
        user_selected_books=["anatomy-and-physiology-2e_-_WEB"],
    )
    assert routed == ["anatomy-and-physiology-2e_-_WEB"]


def test_all_books_mode_routes_endocrine_query():
    """In All Books mode, endocrine query must route to Williams Endocrinology."""
    router = SemanticBookRouter()
    routed = router.route(
        query="What are the clinical manifestations of pheochromocytoma and catecholamine excess?",
        user_selected_books=None,
    )
    assert "Williams_Textbook_of_Endocrinology_15th_edition_2" in routed
    assert len(routed) >= 1


def test_all_books_mode_routes_anatomy_query():
    """In All Books mode, anatomical query must route to Anatomy and Physiology 2e."""
    router = SemanticBookRouter()
    routed = router.route(
        query="What are the borders, boundaries, and neuromuscular contents of the femoral triangle?",
        user_selected_books=None,
    )
    assert "anatomy-and-physiology-2e_-_WEB" in routed
    assert len(routed) >= 1


def test_router_incorporates_clinical_plan():
    """Router leverages ClinicalPlan hypotheses and organ systems when query is brief."""
    router = SemanticBookRouter()
    plan = ClinicalPlan(
        diagnostic_hypotheses=["Addison's Disease", "Primary Adrenal Insufficiency"],
        organ_systems=["Adrenal Cortex", "Endocrinology"],
        search_queries=["adrenal cortex zona glomerulosa cortisol"],
    )
    routed = router.route(
        query="hyperpigmentation and fatigue",
        plan=plan,
        user_selected_books=None,
    )
    assert "Williams_Textbook_of_Endocrinology_15th_edition_2" in routed


def test_extract_referenced_books():
    """Extracts deduplicated book attribution with clean page ranges from citations."""
    citations = [
        CitationRecord(
            citation_id=1,
            book_slug="Williams_Textbook_of_Endocrinology_15th_edition_2",
            section_id=101,
            heading_path="Chapter 15 > Adrenal Glands",
            page_start=624,
            page_end=624,
            chunk_id="chk_1",
        ),
        CitationRecord(
            citation_id=2,
            book_slug="Williams_Textbook_of_Endocrinology_15th_edition_2",
            section_id=102,
            heading_path="Chapter 15 > Biosynthesis",
            page_start=625,
            page_end=628,
            chunk_id="chk_2",
        ),
        CitationRecord(
            citation_id=3,
            book_slug="anatomy-and-physiology-2e_-_WEB",
            section_id=205,
            heading_path="Chapter 17 > Endocrine System",
            page_start=810,
            page_end=810,
            chunk_id="chk_3",
        ),
    ]

    ref_books = extract_referenced_books(citations)
    assert len(ref_books) == 2

    williams = next(b for b in ref_books if "Williams" in b["slug"])
    assert williams["title"] == "Williams Textbook of Endocrinology"
    assert "624" in williams["pages"]
    assert "625–628" in williams["pages"]

    anatomy = next(b for b in ref_books if "anatomy" in b["slug"])
    assert anatomy["title"] == "Anatomy and Physiology 2e"
    assert anatomy["pages"] == "p. 810"


def test_orchestrator_emits_referenced_books_event():
    """Validates that AgentOrchestrator.stream_turn emits 'event: referenced_books'."""
    mock_plan = ClinicalPlan(
        diagnostic_hypotheses=["Thyroiditis"],
        organ_systems=["Endocrinology"],
        search_queries=["thyroid hormone synthesis"],
    )
    mock_planner = MagicMock()
    mock_planner.plan.return_value = mock_plan

    orchestrator = AgentOrchestrator(planner=mock_planner)

    events = []
    for item in orchestrator.stream_turn(
        session_id="test_router_stream_sess",
        user_message="How is thyroid hormone synthesized?",
    ):
        events.append(item)

    event_names = [e.get("event") for e in events]
    assert "referenced_books" in event_names, f"Expected 'referenced_books' in events, got: {event_names}"

    ref_event = next(e for e in events if e.get("event") == "referenced_books")
    ref_data = ref_event["data"]
    assert isinstance(ref_data, list)
    if ref_data:
        assert "title" in ref_data[0]
        assert "slug" in ref_data[0]

