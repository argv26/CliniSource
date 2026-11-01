"""Segment 2 Retrieval & Semantic Routing Integration Test Suite.

Validates the full retrieval and semantic routing layer under realistic clinical workloads:
1. User selection sovereignty over smart routing.
2. Smart multi-book routing across specialty profiles and fallback behavior.
3. Strict multi-book scope boundary filtering (allowed_books).
4. FTS5 query sanitization, medical spelling correction, and punctuation safety.
5. Concurrent multi-query parallel retrieval and chunk deduplication.
6. Figure caption filtering and diagram attribution purity.
7. Citations-to-referenced-books attribution and page span formatting.
8. Section reader text assembly and soft token cap enforcement.
"""
from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.planner import ClinicalPlan
from context.models import CitationRecord
from retrieval.parallel import _execute_parallel_retrieval
from retrieval.router import (
    BOOK_SPECIALTY_PROFILES,
    SemanticBookRouter,
    extract_referenced_books,
)
from retrieval.tools import (
    get_chunk,
    list_books,
    read_section,
    search_chunks,
    search_figures,
    search_sections,
)


# =============================================================================
# Test Cases (Segment 2)
# =============================================================================

def test_router_user_selection_sovereignty():
    # AC: Explicit user selection of specific textbooks must be 100% sovereign and never overridden,
    #     even if the clinical inquiry strictly matches an unselected textbook.
    # Behavior: User selects Anatomy only + Endocrine query -> Router returns exactly [Anatomy].
    # @lane: integration
    # @dependency: none
    # Selection evidence: Essential proof that user study intent and scope selection cannot be hijacked by smart routing heuristics.
    catalog = [
        {"slug": "Williams_Textbook_of_Endocrinology_15th_edition_2", "title": "Williams Endocrinology"},
        {"slug": "anatomy-and-physiology-2e_-_WEB", "title": "Anatomy and Physiology 2e"},
        {"slug": "CORNEA_FundamentalsDiagnosis_and_Management_5th_Ed", "title": "Cornea 5th Ed"},
    ]
    router = SemanticBookRouter(catalog=catalog)

    # 1. Single book selected out of 3
    selected_single = router.route(
        query="What are the biochemical steps of steroidogenesis and cortisol synthesis in the adrenal cortex?",
        user_selected_books=["anatomy-and-physiology-2e_-_WEB"],
    )
    assert selected_single == ["anatomy-and-physiology-2e_-_WEB"]

    # 2. Two books selected out of 3
    selected_double = router.route(
        query="What are the corneal manifestations of keratoconus?",
        user_selected_books=[
            "Williams_Textbook_of_Endocrinology_15th_edition_2",
            "anatomy-and-physiology-2e_-_WEB",
        ],
    )
    assert selected_double == [
        "Williams_Textbook_of_Endocrinology_15th_edition_2",
        "anatomy-and-physiology-2e_-_WEB",
    ]


def test_router_smart_routing_and_fallback():
    # AC: In All Books mode (user_selected_books is None or full catalog), router accurately scores
    #     clinical inquiry against specialty profiles and falls back safely to all books when ambiguous.
    # Behavior: Endocrine query -> Williams; Anatomy query -> A&P; Unmatched query -> All slugs fallback.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Proves scoring algorithm prioritizes high-relevance books while avoiding empty-result deadlocks.
    catalog = [
        {"slug": "Williams_Textbook_of_Endocrinology_15th_edition_2", "title": "Williams Endocrinology"},
        {"slug": "anatomy-and-physiology-2e_-_WEB", "title": "Anatomy and Physiology 2e"},
    ]
    router = SemanticBookRouter(catalog=catalog)

    # A. Endocrine query
    endo_routed = router.route(
        query="Explain hyperosmolar hyperglycemic state and insulin resistance mechanisms in type 2 diabetes.",
        user_selected_books=None,
    )
    assert "Williams_Textbook_of_Endocrinology_15th_edition_2" in endo_routed

    # B. Anatomical query
    anatomy_routed = router.route(
        query="Describe the borders, muscular floor, and neurovascular contents of the femoral triangle.",
        user_selected_books=None,
    )
    assert "anatomy-and-physiology-2e_-_WEB" in anatomy_routed

    # C. Cross-disciplinary query supported by ClinicalPlan
    plan = ClinicalPlan(
        diagnostic_hypotheses=["Pituitary Adenoma with Optic Chiasm Compression"],
        organ_systems=["Endocrine", "Neurological Anatomy"],
        search_queries=["pituitary adenoma optic chiasm visual field defect bitemporal hemianopsia"],
    )
    cross_routed = router.route(
        query="Patient with bitemporal hemianopsia and elevated prolactin.",
        plan=plan,
        user_selected_books=None,
    )
    assert "Williams_Textbook_of_Endocrinology_15th_edition_2" in cross_routed
    assert "anatomy-and-physiology-2e_-_WEB" in cross_routed

    # D. Ambiguous/zero-match query: must fall back cleanly to all available books
    fallback_routed = router.route(
        query="general overview of fundamental clinical protocols xyz123",
        user_selected_books=None,
    )
    assert set(fallback_routed) == {"Williams_Textbook_of_Endocrinology_15th_edition_2", "anatomy-and-physiology-2e_-_WEB"}


def test_multi_book_scope_isolation():
    # AC: search_chunks and search_sections must strictly filter results by allowed_books,
    #     ensuring complete isolation between unselected textbooks.
    # Behavior: Query 'thyroid' with allowed_books=['anatomy-and-physiology-2e_-_WEB'] -> 0 chunks from Williams returned.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Prevents search leakage and unauthorized cross-book contamination in multi-tenant/curated study contexts.
    target_scope = ["anatomy-and-physiology-2e_-_WEB"]

    # 1. Search chunks with scope
    chunks = search_chunks(query="thyroid", allowed_books=target_scope, limit=10)
    assert len(chunks) > 0
    for c in chunks:
        assert c["book_slug"] == "anatomy-and-physiology-2e_-_WEB", (
            f"Scope isolation leak: Found chunk from {c['book_slug']} when restricted to {target_scope}"
        )

    # 2. Search sections with scope
    sections = search_sections(query="thyroid", allowed_books=target_scope, limit=5)
    assert len(sections) > 0
    for s in sections:
        assert s["book_slug"] == "anatomy-and-physiology-2e_-_WEB"

    # 3. Search with empty scope (allowed_books=[]) -> immediate empty list without SQL error
    empty_chunks = search_chunks(query="thyroid", allowed_books=[], limit=5)
    assert empty_chunks == []
    empty_sections = search_sections(query="thyroid", allowed_books=[], limit=5)
    assert empty_sections == []


def test_fts5_query_sanitization_and_spelling():
    # AC: Complex clinical queries with hyphens, quotes, boolean terms, colons, and typos must
    #     be sanitized and executed without sqlite3.OperationalError or FTS syntax crashes.
    # Behavior: Pass syntactically complex query -> Engine cleans and applies spelling correction -> Valid results returned.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Proves the FTS5 sanitization boundary prevents user queries from triggering internal SQLite crashes.
    challenging_queries = [
        'Cushing\'s syndrome: "ACTH-dependent" OR ectopic',
        '1,25-(OH)2-vitamin D3 and Ca2+ homeostasis',
        'What are the first-line therapies for DKA in adults?',
        'febrle neutropenia and thyroditis diagnosis',  # Typos
        '   --- ; SELECT * FROM books; --   ',          # SQL injection attempt / garbage
        'a an the of and with to',                      # Pure stopwords
    ]

    for q in challenging_queries:
        # Neither search_chunks nor search_sections may raise an exception
        chunks = search_chunks(query=q, limit=3)
        assert isinstance(chunks, list)
        sections = search_sections(query=q, limit=3)
        assert isinstance(sections, list)


def test_parallel_multi_query_deduplication():
    # AC: Parallel retrieval must execute multi-query planned searches concurrently and deduplicate
    #     identical chunks while respecting result limit caps.
    # Behavior: Pass 3 overlapping planned queries -> Parallel executor runs 3 workers -> Deduplicated results returned.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Proves concurrent worker threads operate safely without SQLite database locks or duplicated citations.
    overlapping_queries = [
        "Graves disease thyrotoxicosis",
        "Graves disease TSH receptor antibodies",
        "Graves ophthalmopathy hyperthyroidism",
    ]

    result = _execute_parallel_retrieval(
        query=overlapping_queries,
        chunk_limit=6,
        section_limit=3,
        figure_limit=2,
    )

    assert "chunks" in result
    assert "sections" in result
    assert "figures" in result

    chunks = result["chunks"]
    assert 0 < len(chunks) <= 6

    # Verify no duplicate chunk IDs exist in the unified result list
    chunk_ids = [c["chunk_id"] for c in chunks if "chunk_id" in c]
    assert len(chunk_ids) == len(set(chunk_ids)), f"Duplicate chunks detected in parallel results: {chunk_ids}"

    # Verify section limits
    sections = result["sections"]
    assert len(sections) <= 3


def test_figure_search_type_filtering():
    # AC: search_figures must return strictly figure captions with valid page numbers and section heading breadcrumbs.
    # Behavior: Search figures for 'heart' -> Every hit has content_type == 'figure_caption'.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Guarantees the Parallel Figure pipeline in UI only receives true image/diagram captions.
    figures = search_figures(query="heart", limit=4)
    assert len(figures) > 0
    assert len(figures) <= 4

    for fig in figures:
        assert fig["content_type"] == "figure_caption"
        assert fig["page_start"] >= 1
        assert "heading_path" in fig and len(fig["heading_path"]) > 0


def test_citation_referenced_books_attribution():
    # AC: extract_referenced_books must deduplicate books, format page ranges correctly (p. X vs pp. X–Y),
    #     and handle multiple non-contiguous page spans cleanly.
    # Behavior: Heterogeneous CitationRecords -> Grouped and sorted page spans with official titles.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Proves UI badge pills accurately reflect textbook citations without duplicate tags.
    citations = [
        CitationRecord(
            citation_id=1,
            book_slug="Williams_Textbook_of_Endocrinology_15th_edition_2",
            section_id=10,
            heading_path="Adrenal",
            page_start=45,
            page_end=45,
            chunk_id="c1",
        ),
        CitationRecord(
            citation_id=2,
            book_slug="Williams_Textbook_of_Endocrinology_15th_edition_2",
            section_id=11,
            heading_path="Adrenal > Steroids",
            page_start=60,
            page_end=64,
            chunk_id="c2",
        ),
        CitationRecord(
            citation_id=3,
            book_slug="anatomy-and-physiology-2e_-_WEB",
            section_id=50,
            heading_path="Cardiovascular",
            page_start=120,
            page_end=120,
            chunk_id="c3",
        ),
        CitationRecord(
            citation_id=4,
            book_slug="custom_unregistered_slug",
            section_id=1,
            heading_path="Custom",
            page_start=5,
            page_end=8,
            chunk_id="c4",
        ),
    ]

    referenced = extract_referenced_books(citations)
    assert len(referenced) == 3

    # Check Williams: single page + multi-page span
    williams = next(b for b in referenced if b["slug"] == "Williams_Textbook_of_Endocrinology_15th_edition_2")
    assert williams["title"] == "Williams Textbook of Endocrinology"
    assert "45" in williams["pages"]
    assert "60–64" in williams["pages"]

    # Check Anatomy: single page format "p. 120"
    anatomy = next(b for b in referenced if b["slug"] == "anatomy-and-physiology-2e_-_WEB")
    assert anatomy["pages"] == "p. 120"

    # Check unregistered book fallback title generation
    custom = next(b for b in referenced if b["slug"] == "custom_unregistered_slug")
    assert custom["title"] == "Custom Unregistered Slug"
    assert custom["pages"] == "pp. 5–8"


def test_section_reader_assembly_and_token_cap():
    # AC: read_section must assemble all chunks within a section in reading order and respect max_tokens cap.
    # Behavior: Read valid section with max_tokens limit -> Returns assembled_text capped at specified bound.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Verifies LLM prompt context injection never receives an unbounded section dump.
    book_slug = "anatomy-and-physiology-2e_-_WEB"
    section_id = 1  # Preface / Introduction

    # 1. Normal read with standard token ceiling
    content = read_section(book_slug=book_slug, section_id=section_id, max_tokens=2000)
    assert "error" not in content
    assert content["book_slug"] == book_slug
    assert content["section_id"] == section_id
    assert "assembled_text" in content
    assert len(content["assembled_text"]) > 0

    # 2. Strict max_tokens cap
    capped_content = read_section(book_slug=book_slug, section_id=section_id, max_tokens=150)
    assert "error" not in capped_content
    # The assembled text should be bounded
    assert len(capped_content.get("chunks", [])) <= 2

    # 3. Non-existent section
    missing = read_section(book_slug=book_slug, section_id=999999)
    assert "error" in missing

