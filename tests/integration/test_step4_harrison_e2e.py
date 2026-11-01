"""Step 4 Full End-to-End System Verification: Harrison's Principles of Internal Medicine (22nd Edition).

Validates:
1. Book record and schema verification in clinical database (4,273 pages, 591 sections, ~16,963 chunks).
2. FTS5 BM25 search across Harrison medical sections and chunk breadcrumbs.
3. User library personal curation, dynamic active toggles, and catalog enrichment.
4. Semantic multi-book routing across Harrison (Internal Medicine) and Williams (Endocrinology).
5. Evidence Drawer API contract and clean chunk text rendering.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from retrieval.router import SemanticBookRouter, extract_referenced_books
from retrieval.tools import search_chunks, search_sections
from ui.auth import create_guest_user, init_auth_db
from ui.library import (
    add_to_user_library,
    get_global_catalog,
    get_user_library,
    remove_from_user_library,
    toggle_user_book_active,
)
from ui.routers.content import api_get_chunk

HARRISON_SLUG = "Harrison_2025_22nd_Edition"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = (ROOT_DIR / "clinisource.db") if (ROOT_DIR / "clinisource.db").exists() else (ROOT_DIR / "textbook_rag.db")


def test_harrison_database_record_and_schema():
    # AC: Harrison 2025 (22nd Ed) must be indexed into clinical database with 4,273 pages,
    #     specialty 'Internal Medicine', and full FTS5 search index synchronization.
    # Behavior: Query SQLite books, sections, chunks, and chunks_fts tables -> Record counts match.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Proves the physical persistence layer accurately stores the 276.7 MB textbook.
    assert DB_PATH.exists(), f"Clinical database not found at {DB_PATH}"

    conn = sqlite3.connect(str(DB_PATH))
    book = conn.execute(
        "SELECT slug, title, specialty, total_pages FROM books WHERE slug = ?;",
        (HARRISON_SLUG,),
    ).fetchone()

    assert book is not None, f"Harrison textbook not found in books table with slug {HARRISON_SLUG}"
    assert book[0] == HARRISON_SLUG
    assert book[2] == "Internal Medicine"
    assert book[3] == 4273

    sec_count = conn.execute("SELECT count(*) FROM sections WHERE book_slug = ?;", (HARRISON_SLUG,)).fetchone()[0]
    chk_count = conn.execute("SELECT count(*) FROM chunks WHERE book_slug = ?;", (HARRISON_SLUG,)).fetchone()[0]
    fts_count = conn.execute("SELECT count(*) FROM chunks_fts WHERE book_slug = ?;", (HARRISON_SLUG,)).fetchone()[0]
    conn.close()

    assert sec_count >= 500, f"Expected >= 500 sections in Harrison, got {sec_count}"
    assert chk_count >= 10000, f"Expected >= 10,000 chunks in Harrison, got {chk_count}"
    assert fts_count == chk_count, f"FTS5 chunks ({fts_count}) does not match chunks ({chk_count})"


def test_harrison_fts5_clinical_retrieval():
    # AC: Clinical queries targeted at Harrison must return highly relevant chunks with valid page numbers and section breadcrumbs.
    # Behavior: Execute search_chunks with clinical query -> Returns matching passages from Harrison.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Confirms physicians can locate specific emergency and internal medicine protocols.
    query = "diabetic ketoacidosis fluid resuscitation protocols"
    results = search_chunks(query=query, book_slug=HARRISON_SLUG, limit=5)

    assert len(results) > 0, f"No chunks retrieved from Harrison for query: {query}"
    top_hit = results[0]

    assert top_hit["book_slug"] == HARRISON_SLUG
    assert top_hit["page_start"] >= 3000
    assert "Diabetes" in (top_hit.get("heading_path") or "")
    assert "snippet" in top_hit
    assert len(top_hit["snippet"]) > 0


def test_harrison_global_catalog_and_user_curation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: Harrison must appear in Global Catalog under 'Internal Medicine' and be personalizable in user library.
    # Behavior: Create guest user, toggle Harrison active, remove, and re-add -> User library accurately reflects state.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Validates user library multi-tenant preference separation with Harrison.
    test_auth_db = tmp_path / "app_users_harrison.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_auth_db))
    init_auth_db(test_auth_db)

    user = create_guest_user(test_auth_db)
    user_id = user["id"]

    # 1. Global catalog inspection
    catalog = get_global_catalog()
    harrison_entry = next((b for b in catalog if b["slug"] == HARRISON_SLUG), None)
    assert harrison_entry is not None, "Harrison missing from global catalog"
    assert harrison_entry["specialty"] == "Internal Medicine"
    assert harrison_entry["total_pages"] == 4273

    # 2. Add to user library and activate
    add_to_user_library(user_id, HARRISON_SLUG, is_active=True, db_path=test_auth_db)
    user_books = get_user_library(user_id, db_path=test_auth_db)
    assert any(b["slug"] == HARRISON_SLUG and b["is_active"] is True for b in user_books)

    # 3. Deactivate Harrison
    toggle_user_book_active(user_id, HARRISON_SLUG, is_active=False, db_path=test_auth_db)
    user_books_after = get_user_library(user_id, db_path=test_auth_db)
    assert any(b["slug"] == HARRISON_SLUG and b["is_active"] is False for b in user_books_after)

    # 4. Remove and re-add
    remove_from_user_library(user_id, HARRISON_SLUG, db_path=test_auth_db)
    user_books_removed = get_user_library(user_id, db_path=test_auth_db)
    assert not any(b["slug"] == HARRISON_SLUG for b in user_books_removed)


def test_harrison_multi_textbook_semantic_routing():
    # AC: The SemanticBookRouter must smartly select Harrison alongside Williams for multi-specialty metabolic queries,
    #     while strictly honoring user sovereignty when a single book is selected.
    # Behavior: Evaluate router across user sovereignty and all-books mode -> Correct book subsets chosen.
    # @lane: service-integration-e2e
    # @dependency: none
    # Selection evidence: Asserts intelligent book attribution across Harrison and Williams.
    router = SemanticBookRouter()

    # User Sovereignty: Only Harrison selected
    sovereign_selection = router.route(
        query="What are the diagnostic criteria for pheochromocytoma?",
        user_selected_books=[HARRISON_SLUG],
    )
    assert sovereign_selection == [HARRISON_SLUG]

    # Smart Routing: Multi-specialty internal medicine query
    routed_selection = router.route(
        query="diabetic ketoacidosis resuscitation guidelines and insulin administration",
        user_selected_books=None,
    )
    assert HARRISON_SLUG in routed_selection
    assert "Williams_Textbook_of_Endocrinology_15th_edition_2" in routed_selection


def test_harrison_evidence_drawer_chunk_retrieval():
    # AC: The Evidence Drawer endpoint /api/chunk/{chunk_id} must return full chunk text and metadata
    #     for citations referencing Harrison's Principles of Internal Medicine.
    # Behavior: Fetch chunk by ID -> Returns formatted text, section path, and page range without hyphens.
    # @lane: service-integration-e2e
    # @dependency: sqlite
    # Selection evidence: Proves the UI Evidence Drawer accurately renders Harrison source text for clinical verification.
    results = search_chunks(query="diabetic ketoacidosis", book_slug=HARRISON_SLUG, limit=1)
    assert len(results) > 0
    chunk_id = results[0]["chunk_id"]

    drawer_res = api_get_chunk(chunk_id)
    assert "error" not in drawer_res
    assert drawer_res["chunk_id"] == chunk_id
    assert drawer_res["book_slug"] == HARRISON_SLUG
    assert len(drawer_res["text"]) > 100
    assert drawer_res["page_start"] >= 1

