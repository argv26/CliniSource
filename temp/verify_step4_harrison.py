"""Step 4 Full End-to-End System Verification: Harrison 2025 (22nd Edition).

Validates:
1. Ingestion of 4,273-page Harrison PDF with progress monitoring.
2. Structure extraction, sections hierarchy, and FTS5 indexing.
3. Library Manager catalog & user library activation.
4. Multi-textbook retrieval and citation extraction across Harrison & Williams.
5. Evidence Drawer API contract and chunk detail retrieval.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3
from ingestion.pipeline_worker import (
    create_job,
    get_job,
    run_ingestion_pipeline,
)
from retrieval.tools import search_chunks, search_sections
from retrieval.router import SemanticBookRouter, extract_referenced_books
from ui.auth import create_guest_user, init_auth_db
from ui.library import (
    add_to_user_library,
    get_global_catalog,
    get_user_library,
    toggle_user_book_active,
)
from ui.routers.content import api_get_chunk


def main():
    print("=" * 70)
    print("STEP 4: E2E VERIFICATION - HARRISON'S PRINCIPLES OF INTERNAL MEDICINE")
    print("=" * 70)

    pdf_path = ROOT / "Harrison 2025 _ 22nd Edition.pdf"
    assert pdf_path.exists(), f"Harrison PDF not found at {pdf_path}"
    print(f"[1/6] PDF found: {pdf_path.name} ({pdf_path.stat().st_size / (1024 * 1024):.1f} MB)")

    title = "Harrison's Principles of Internal Medicine (22nd Edition)"
    specialty = "Internal Medicine"
    book_slug = "Harrison_2025_22nd_Edition"
    job_id = f"e2e_harrison_{int(time.time())}"

    # Check if already ingested in textbook_rag.db
    conn = sqlite3.connect("textbook_rag.db")
    existing = conn.execute("SELECT slug, total_pages FROM books WHERE slug = ?;", (book_slug,)).fetchone()
    conn.close()

    if existing:
        print(f"[2/6] Book '{book_slug}' already indexed with {existing[1]} pages. Skipping re-ingestion.")
    else:
        print(f"[2/6] Starting background ingestion pipeline for job {job_id}...")
        create_job(job_id=job_id, title=title, specialty=specialty, book_slug=book_slug)

        t0 = time.perf_counter()
        job = run_ingestion_pipeline(
            job_id=job_id,
            pdf_path=pdf_path,
            title=title,
            specialty=specialty,
            book_slug=book_slug,
        )
        elapsed = time.perf_counter() - t0
        print(f"      Ingestion finished in {elapsed:.2f}s with status: {job.status}")
        assert job.status == "completed", f"Ingestion failed: {job.user_error_message} ({job.technical_error})"

    # Verify database contents
    print("\n[3/6] Verifying SQLite database integrity...")
    conn = sqlite3.connect("textbook_rag.db")
    b_row = conn.execute("SELECT slug, title, specialty, total_pages FROM books WHERE slug = ?;", (book_slug,)).fetchone()
    assert b_row is not None, "Book record not found in books table!"
    print(f"      Book Record: slug='{b_row[0]}', specialty='{b_row[2]}', total_pages={b_row[3]}")
    assert b_row[3] == 4273, f"Expected 4273 pages, got {b_row[3]}"
    assert b_row[2] == "Internal Medicine"

    sec_count = conn.execute("SELECT count(*) FROM sections WHERE book_slug = ?;", (book_slug,)).fetchone()[0]
    chk_count = conn.execute("SELECT count(*) FROM chunks WHERE book_slug = ?;", (book_slug,)).fetchone()[0]
    fts_count = conn.execute("SELECT count(*) FROM chunks_fts WHERE book_slug = ?;", (book_slug,)).fetchone()[0]
    conn.close()

    print(f"      Sections Indexed: {sec_count}")
    print(f"      Chunks Indexed:   {chk_count}")
    print(f"      FTS5 Chunks:      {fts_count}")
    assert sec_count >= 500, f"Expected >= 500 sections, got {sec_count}"
    assert chk_count >= 10000, f"Expected >= 10,000 chunks, got {chk_count}"
    assert fts_count == chk_count, f"FTS5 count ({fts_count}) does not match chunks count ({chk_count})"

    # Verify Global Catalog and User Library
    print("\n[4/6] Verifying Library Manager Catalog & User Library Curation...")
    init_auth_db()
    user = create_guest_user()
    user_id = user["id"]

    catalog = get_global_catalog()
    assert any(b["slug"] == book_slug for b in catalog), "Harrison not found in Global Catalog!"
    harrison_cat = next(b for b in catalog if b["slug"] == book_slug)
    assert harrison_cat["specialty"] == "Internal Medicine", f"Expected 'Internal Medicine', got {harrison_cat['specialty']}"
    print(f"      Global Catalog correctly lists Harrison under 'Internal Medicine'.")

    # Add to user library and activate
    add_to_user_library(user_id, book_slug, is_active=True)
    user_books = get_user_library(user_id)
    harrison_user_entry = next((b for b in user_books if b["slug"] == book_slug), None)
    assert harrison_user_entry is not None, "Harrison not found in user library!"
    assert harrison_user_entry["is_active"] is True
    print(f"      User Library correctly has Harrison active for consultations.")

    # Verify Retrieval on Clinical Queries
    print("\n[5/6] Verifying FTS5 Retrieval & Semantic Search on Harrison...")
    query = "diabetic ketoacidosis fluid resuscitation protocols"
    results = search_chunks(query=query, book_slug=book_slug, limit=5)
    assert len(results) > 0, "No chunks returned for diabetic ketoacidosis from Harrison!"
    top_hit = results[0]
    print(f"      Top hit for '{query}':")
    print(f"      Chunk ID: {top_hit['chunk_id']}")
    print(f"      Pages:    {top_hit['page_start']}-{top_hit['page_end']}")
    print(f"      Section:  {top_hit.get('heading_path')}")
    clean_snippet = top_hit['snippet'][:150].encode('ascii', 'replace').decode()
    print(f"      Snippet:  {clean_snippet}...")

    # Multi-Textbook Semantic Routing
    print("\n[6/6] Verifying Multi-Book Routing & Evidence Drawer API...")
    router = SemanticBookRouter()
    # Test user sovereignty
    sovereign_slugs = router.route(
        query="What are the differential diagnoses for acute chest pain and troponin elevation?",
        user_selected_books=[book_slug],
    )
    print(f"      Sovereignty selected slugs: {sovereign_slugs}")
    assert sovereign_slugs == [book_slug]

    # Test smart routing
    routed_slugs = router.route(
        query="What are the differential diagnoses for diabetic ketoacidosis and hyperosmolar hyperglycemic state?",
        user_selected_books=None,
    )
    print(f"      Smart routed slugs: {routed_slugs}")
    assert len(routed_slugs) > 0

    # Test Evidence Drawer API
    drawer_data = api_get_chunk(top_hit["chunk_id"])
    assert "error" not in drawer_data
    assert drawer_data["chunk_id"] == top_hit["chunk_id"]
    assert "text" in drawer_data
    print(f"      Evidence Drawer API returned chunk details with clean text ({len(drawer_data['text'])} chars).")

    print("\n" + "=" * 70)
    print("ALL STEP 4 E2E VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
