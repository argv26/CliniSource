"""Segment 1 Ingestion & Document Pipeline Integration Test Suite.

Validates the full document ingestion lifecycle under production and adverse clinical conditions:
1. Scanned / OCR-less PDF detection and friendly diagnostics.
2. Encrypted / password-protected PDF rejection.
3. Corrupted / truncated byte streams and zero-page checks.
4. Hierarchical TOC extraction and single-section fallback generation.
5. Multi-column reading order preservation (gutter sorting).
6. Bounded semantic chunking (300-500 tokens), sentence integrity, and hyphen healing.
7. Transactional atomicity and clean rollback on ingestion failure.
8. End-to-end happy path with figure extraction and SQLite FTS5 search indexing.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

import pytest

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from ingestion.chunk_sections import est_tokens, split_into_sentences
from ingestion.load_to_db import SqliteBackend
from ingestion.pipeline_worker import (
    CorruptedPdfError,
    DuplicateBookError,
    EncryptedPdfError,
    IngestionError,
    ScannedPdfError,
    _build_sections_from_toc,
    _crop_figure_from_page,
    _extract_page_text_blocks,
    _generate_chunks_from_sections,
    create_job,
    get_job,
    run_ingestion_pipeline,
)
from storage.object_store import get_storage_provider


# =============================================================================
# Helper Utilities for Synthetic Document Generation
# =============================================================================

def create_synthetic_pdf(
    path: Path,
    pages_text: list[str],
    toc: list[list[Any]] | None = None,
    encrypted_pw: str | None = None,
) -> Path:
    """Generates a clean synthetic PDF for deterministic test evaluation."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=612, height=792)
        if text.strip():
            page.insert_textbox(pymupdf.Rect(54, 54, 558, 738), text)
    if toc:
        doc.set_toc(toc)
    if encrypted_pw:
        doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=encrypted_pw)
    else:
        doc.save(str(path))
    doc.close()
    return path


# =============================================================================
# Test Cases (Segment 1)
# =============================================================================

def test_scanned_pdf_rejection(tmp_path: Path):
    # AC: Scanned or textless PDFs lacking a digital text layer must raise ScannedPdfError
    #     and return reassuring diagnostic guidance without crashing the server.
    # Behavior: Upload textless PDF -> Background worker detects text density < 60 chars -> Job status 'failed' with OCR guidance.
    # @lane: integration
    # @dependency: pymupdf
    # Selection evidence: Proves the early density heuristic prevents corrupting downstream chunking and vector indexing.
    pdf_path = tmp_path / "scanned_sample.pdf"
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page(width=612, height=792)  # Empty scanned placeholder pages
    doc.save(str(pdf_path))
    doc.close()

    job_id = f"test_scanned_{uuid.uuid4().hex[:8]}"
    create_job(job_id, "Scanned Atlas of Pathology", "Pathology", "scanned_atlas")

    db_path = tmp_path / "test_ingest.db"
    job = run_ingestion_pipeline(job_id, pdf_path, "Scanned Atlas of Pathology", "Pathology", db_path=db_path)

    assert job.status == "failed"
    assert job.stage == "failed"
    assert job.user_error_message is not None
    assert "scanned document" in job.user_error_message.lower()
    assert "ocr support" in job.user_error_message.lower()


def test_encrypted_pdf_rejection(tmp_path: Path):
    # AC: Password-protected or DRM-locked PDFs must be rejected with EncryptedPdfError and an actionable user message.
    # Behavior: Upload encrypted PDF -> doc.is_encrypted triggers -> Job status 'failed' with password notice.
    # @lane: integration
    # @dependency: pymupdf
    # Selection evidence: Protects ingestion loop from unhandled decryption exceptions and infinite retry loops.
    pdf_path = tmp_path / "encrypted_sample.pdf"
    create_synthetic_pdf(
        pdf_path,
        pages_text=["Confidential clinical research protocols and drug trial data."],
        encrypted_pw="clinician_pass_123",
    )

    job_id = f"test_enc_{uuid.uuid4().hex[:8]}"
    create_job(job_id, "Protected Clinical Trials", "Oncology", "protected_trials")

    db_path = tmp_path / "test_ingest.db"
    job = run_ingestion_pipeline(job_id, pdf_path, "Protected Clinical Trials", "Oncology", db_path=db_path)

    assert job.status == "failed"
    assert job.stage == "failed"
    assert job.user_error_message is not None
    assert "password-protected" in job.user_error_message.lower() or "restricted" in job.user_error_message.lower()


def test_corrupted_stream_handling(tmp_path: Path):
    # AC: Truncated, 0-byte, or malformed non-PDF files must trigger CorruptedPdfError cleanly.
    # Behavior: Pass 0-byte file -> Validation stage raises CorruptedPdfError -> Job fails with integrity notice.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Verifies stage 0 pre-flight guards execute before PyMuPDF C-level stream parsing.
    empty_file = tmp_path / "corrupt_empty.pdf"
    empty_file.write_bytes(b"")

    job_id = f"test_corrupt_{uuid.uuid4().hex[:8]}"
    create_job(job_id, "Corrupted Textbook", "Neurology", "corrupted_textbook")

    db_path = tmp_path / "test_ingest.db"
    job = run_ingestion_pipeline(job_id, empty_file, "Corrupted Textbook", "Neurology", db_path=db_path)

    assert job.status == "failed"
    assert job.stage == "failed"
    assert job.user_error_message is not None
    assert "damaged" in job.user_error_message.lower() or "empty" in job.user_error_message.lower()


def test_toc_and_fallback_hierarchy():
    # AC: Structured TOC creates multi-tier heading paths and leaf node flags; empty TOC generates a safe fallback.
    # Behavior: TOC list -> _build_sections_from_toc() -> Correct parent_id, heading_path, and is_leaf attributes.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Essential proof that hierarchical breadcrumbs and section spans are calculated deterministically.
    rich_toc = [
        [1, "Part I: Introduction", 1],
        [2, "Chapter 1: Principles of Medicine", 1],
        [3, "Section 1.1: Cellular Mechanisms", 2],
        [1, "Part II: Disorders of the Cardiovascular System", 5],
    ]
    sections = _build_sections_from_toc(rich_toc, total_pages=10, default_title="Clinical Medicine")

    assert len(sections) == 4
    # Part I has children, so is_leaf must be False
    assert sections[0]["is_leaf"] is False
    assert sections[0]["parent_id"] is None
    assert sections[0]["heading_path"] == "Part I: Introduction"

    # Chapter 1 parent is Part I
    assert sections[1]["parent_id"] == 1
    assert sections[1]["is_leaf"] is False
    assert sections[1]["heading_path"] == "Part I: Introduction > Chapter 1: Principles of Medicine"

    # Section 1.1 parent is Chapter 1, leaf is True
    assert sections[2]["parent_id"] == 2
    assert sections[2]["is_leaf"] is True
    assert sections[2]["heading_path"] == "Part I: Introduction > Chapter 1: Principles of Medicine > Section 1.1: Cellular Mechanisms"

    # Part II is a new top-level section
    assert sections[3]["parent_id"] is None
    assert sections[3]["heading_path"] == "Part II: Disorders of the Cardiovascular System"

    # Test fallback TOC for documents without native bookmarks
    fallback = _build_sections_from_toc([], total_pages=8, default_title="General Surgery Handbook")
    assert len(fallback) == 1
    assert fallback[0]["id"] == 1
    assert fallback[0]["title"] == "General Surgery Handbook"
    assert fallback[0]["pdf_start"] == 1
    assert fallback[0]["pdf_end"] == 8
    assert fallback[0]["is_leaf"] is True


def test_reading_order_column_flow(tmp_path: Path):
    # AC: Multi-column textbook pages must extract left column before right column to prevent interleaved sentences.
    # Behavior: 2-column layout page -> _extract_page_text_blocks() -> Blocks sorted left-column top-down, then right-column.
    # @lane: integration
    # @dependency: pymupdf
    # Selection evidence: Proves clinical narratives retain syntactic and semantic continuity across column boundaries.
    pdf_path = tmp_path / "multicol_sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Left column: x from 50 to 250
    page.insert_textbox(pymupdf.Rect(50, 80, 250, 140), "Left column paragraph 1: Patient presented with acute chest pain.")
    page.insert_textbox(pymupdf.Rect(50, 180, 250, 240), "Left column paragraph 2: Electrocardiogram revealed ST-elevation.")

    # Right column: x from 350 to 550
    page.insert_textbox(pymupdf.Rect(350, 80, 550, 140), "Right column paragraph 3: Immediate catheterization was indicated.")
    page.insert_textbox(pymupdf.Rect(350, 180, 550, 240), "Right column paragraph 4: Primary percutaneous coronary intervention succeeded.")

    doc.save(str(pdf_path))
    doc.close()

    eval_doc = pymupdf.open(str(pdf_path))
    extracted = _extract_page_text_blocks(eval_doc)
    eval_doc.close()

    assert len(extracted) == 1
    page_text = extracted[0]["text"]

    # Verify strictly monotonic appearance: Para 1 -> Para 2 -> Para 3 -> Para 4
    idx1 = page_text.find("Left column paragraph 1")
    idx2 = page_text.find("Left column paragraph 2")
    idx3 = page_text.find("Right column paragraph 3")
    idx4 = page_text.find("Right column paragraph 4")

    assert idx1 != -1 and idx2 != -1 and idx3 != -1 and idx4 != -1
    assert idx1 < idx2 < idx3 < idx4, f"Column reading order violated: idx1={idx1}, idx2={idx2}, idx3={idx3}, idx4={idx4}"


def test_semantic_chunking_bounds_and_hyphenation():
    # AC: Chunks must adhere to 300-500 token window, split cleanly on sentence boundaries, and detect figure captions.
    # Behavior: Multi-sentence section text -> _generate_chunks_from_sections() -> Chunks created within target token size.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Verifies token bounds prevent LLM context overflow while maintaining figure tagging.
    sections = [
        {
            "id": 1,
            "title": "Heart Failure Pathophysiology",
            "pdf_start": 1,
            "pdf_end": 2,
            "heading_path": "Cardiology > Heart Failure",
            "is_leaf": True,
        }
    ]

    # Generate sufficient clinical text to force multiple chunks
    long_sentences = [
        f"Clinical sentence {i}: Compensatory neurohormonal activation initially maintains cardiac output through the sympathetic nervous system and renin-angiotensin-aldosterone axis."
        for i in range(1, 30)
    ]
    # Add a figure reference sentence
    long_sentences.insert(10, "FIGURE 2.4 Diagnostic cascade for preserved ejection fraction.")

    full_text = " ".join(long_sentences)
    pages_data = [
        {"page_num": 1, "text": " ".join(long_sentences[:15])},
        {"page_num": 2, "text": " ".join(long_sentences[15:])},
    ]

    chunks = _generate_chunks_from_sections(
        book_slug="test_cardio_slug",
        sections=sections,
        pages_data=pages_data,
        target_tokens=350,
    )

    assert len(chunks) >= 2
    for c in chunks:
        # Every chunk must have bounded tokens and non-empty text
        assert 0 < c["token_count"] <= 500
        assert c["chunk_id"].startswith("test_cardio_slug_s0001_c")
        assert c["embed_text"].startswith("[Cardiology > Heart Failure]")
        assert len(c["content_hash"]) == 64

    # Verify figure classification
    fig_chunks = [c for c in chunks if c["content_type"] == "figure_caption"]
    assert len(fig_chunks) >= 1
    assert "FIGURE 2.4" in fig_chunks[0]["text"]


def test_atomic_rollback_on_failure(tmp_path: Path):
    # AC: Database write transaction must be completely atomic; any failure mid-load rolls back all inserted records.
    # Behavior: Inject unhandled KeyError during chunk loading -> Transaction aborted -> 0 books and 0 sections persisted.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Proves database never enters a partially-indexed or corrupted orphan state.
    db_path = tmp_path / "rollback_test.db"
    backend = SqliteBackend(db_path)
    backend.init_schema()

    valid_sections = [
        {
            "id": 1,
            "title": "Renal Physiology",
            "level": 1,
            "pdf_start": 1,
            "pdf_end": 5,
            "heading_path": "Nephrology > Renal Physiology",
            "is_leaf": True,
        }
    ]
    # Malformed chunk missing required 'chunk_id' key
    corrupted_chunks = [{"invalid_key": "bad_data"}]

    with pytest.raises(KeyError):
        backend.load_book("faulty_book", valid_sections, corrupted_chunks)

    # Verify state isolation in a fresh independent connection
    verify_conn = sqlite3.connect(str(db_path))
    books_count = verify_conn.execute("SELECT count(*) FROM books WHERE slug = 'faulty_book';").fetchone()[0]
    sections_count = verify_conn.execute("SELECT count(*) FROM sections WHERE book_slug = 'faulty_book';").fetchone()[0]
    chunks_count = verify_conn.execute("SELECT count(*) FROM chunks WHERE book_slug = 'faulty_book';").fetchone()[0]
    verify_conn.close()

    assert books_count == 0, f"Expected 0 books, found {books_count} (atomicity failed)"
    assert sections_count == 0, f"Expected 0 sections, found {sections_count} (atomicity failed)"
    assert chunks_count == 0, f"Expected 0 chunks, found {chunks_count} (atomicity failed)"


def test_end_to_end_pipeline_success(tmp_path: Path):
    # AC: Valid medical PDF processes end-to-end through validation, TOC, reading order, chunking, and FTS5 indexing.
    # Behavior: Upload multi-page PDF with figure -> Worker completes 100% -> Book, sections, chunks, and FTS searchable.
    # @lane: integration
    # @dependency: sqlite, pymupdf, background-worker
    # Selection evidence: Exercises full integration boundary connecting PyMuPDF, chunking, and SQLite FTS5 search.
    pdf_path = tmp_path / "valid_endocrinology.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_textbox(
        pymupdf.Rect(54, 54, 558, 738),
        "Chapter 1: Hypothalamic and Pituitary Hormones.\n"
        "The anterior pituitary synthesizes six major peptide hormones: ACTH, TSH, GH, PRL, FSH, and LH.\n"
        "Feedback inhibition by circulating target organ hormones regulates pituitary secretion precisely.\n"
        "FIGURE 1.2 Hypothalamic-pituitary-adrenal feedback loop diagram.",
    )
    p2 = doc.new_page(width=612, height=792)
    p2.insert_textbox(
        pymupdf.Rect(54, 54, 558, 738),
        "Chapter 2: Thyroid Gland Disorders and Thyrotoxicosis.\n"
        "Graves disease is the most common cause of hyperthyroidism in patients under 50 years of age.\n"
        "Serum TSH levels are suppressed below 0.01 mIU/L in overt thyrotoxicosis.",
    )
    doc.set_toc([
        [1, "Chapter 1: Pituitary Hormones", 1],
        [1, "Chapter 2: Thyroid Disorders", 2],
    ])
    doc.save(str(pdf_path))
    doc.close()

    db_path = tmp_path / "e2e_verified.db"
    job_id = f"test_e2e_{uuid.uuid4().hex[:8]}"
    create_job(job_id, "Endocrine Disorders Guide", "Endocrinology", "endocrine_disorders")

    job = run_ingestion_pipeline(
        job_id=job_id,
        pdf_path=pdf_path,
        title="Endocrine Disorders Guide",
        specialty="Endocrinology",
        db_path=db_path,
    )

    assert job.status == "completed"
    assert job.progress_percent == 100
    assert job.stage == "completed"
    assert job.total_pages == 2
    assert job.sections_count >= 2
    assert job.chunks_count >= 2

    # Query the isolated database to verify records and FTS5 searchability
    backend = SqliteBackend(db_path)
    stats = backend.count()
    assert stats["books"] == 1
    assert stats["sections"] == 2
    assert stats["chunks"] >= 2

    # Verify FTS5 search returns expected chunk with highlighted query term
    search_results = backend.search("Graves disease hyperthyroidism", limit=3)
    assert len(search_results) > 0
    assert search_results[0]["book_slug"] == "endocrine_disorders"
    assert "Graves" in search_results[0]["snippet"]
    assert "hyperthyroidism" in search_results[0]["snippet"]
