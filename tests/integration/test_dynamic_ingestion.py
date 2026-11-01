"""Integration tests for Dynamic Ingestion Service and Upload Endpoints."""
from __future__ import annotations

import io
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from ui.app import app
from retrieval.tools import search_chunks
from ingestion.pipeline_worker import run_ingestion_pipeline, create_job, get_job


@pytest.fixture
def client():
    return TestClient(app)


def _create_synthetic_clinical_pdf(tmp_path: Path) -> Path:
    """Creates a lightweight 3-page clinical PDF with headings and text."""
    pdf_path = tmp_path / "synthetic_cardiology.pdf"
    doc = pymupdf.open()

    # Page 1: Chapter 1
    p1 = doc.new_page()
    p1.insert_text((50, 70), "Chapter 1: Clinical Principles of Cardiac Arrhythmias", fontsize=16)
    p1.insert_textbox(
        pymupdf.Rect(50, 90, 550, 300),
        "Cardiac arrhythmias encompass a wide spectrum of conduction abnormalities. "
        "The sinoatrial node serves as the physiologic pacemaker of the healthy heart. "
        "Depolarization waves traverse the atria toward the atrioventricular node.",
        fontsize=11,
    )

    # Page 2: Section 1.1
    p2 = doc.new_page()
    p2.insert_text((50, 70), "Section 1.1: Ventricular Tachycardia and Fibrillation", fontsize=14)
    p2.insert_textbox(
        pymupdf.Rect(50, 90, 550, 300),
        "Ventricular tachycardia represents a potentially life-threatening ventricular rhythm. "
        "Immediate cardioversion or antiarrhythmic pharmacotherapy is indicated for hemodynamic instability. "
        "Amiodarone and lidocaine are standard first-line therapies.",
        fontsize=11,
    )

    # Page 3: Section 1.2
    p3 = doc.new_page()
    p3.insert_text((50, 70), "Section 1.2: Supraventricular Tachycardia Diagnosis", fontsize=14)
    p3.insert_textbox(
        pymupdf.Rect(50, 90, 550, 300),
        "Supraventricular tachycardia frequently presents with sudden-onset palpitations. "
        "Vagal maneuvers or intravenous adenosine can terminate reentrant AV nodal pathways safely.",
        fontsize=11,
    )

    doc.set_toc([
        [1, "Chapter 1: Clinical Principles of Cardiac Arrhythmias", 1],
        [2, "Section 1.1: Ventricular Tachycardia and Fibrillation", 2],
        [2, "Section 1.2: Supraventricular Tachycardia Diagnosis", 3],
    ])
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_upload_non_pdf_rejected(client: TestClient):
    """Uploading non-PDF files must return HTTP 400 Bad Request."""
    file_content = b"This is a text file."
    files = {"file": ("notes.txt", io.BytesIO(file_content), "text/plain")}
    data = {"title": "Clinical Notes", "specialty": "Internal Medicine"}
    res = client.post("/api/books/upload", data=data, files=files)
    assert res.status_code == 400
    assert "Only PDF files" in res.json()["detail"]


def test_upload_corrupt_pdf_rejected(client: TestClient):
    """Uploading a file named .pdf without PDF magic bytes must return HTTP 400."""
    corrupt_content = b"Not a real PDF stream at all."
    files = {"file": ("damaged.pdf", io.BytesIO(corrupt_content), "application/pdf")}
    data = {"title": "Damaged Book", "specialty": "Neurology"}
    res = client.post("/api/books/upload", data=data, files=files)
    assert res.status_code == 400
    assert "Missing %PDF header bytes" in res.json()["detail"]


def test_upload_duplicate_book_rejected(client: TestClient):
    """Uploading a book title matching an existing indexed book must return HTTP 409 Conflict."""
    valid_pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    files = {"file": ("anatomy.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    data = {"title": "Anatomy and Physiology 2e", "specialty": "Anatomy"}
    res = client.post("/api/books/upload", data=data, files=files)
    assert res.status_code == 409
    assert "already exists in the Global Library" in res.json()["detail"]


def test_dynamic_ingestion_end_to_end(client: TestClient, tmp_path: Path):
    """Verifies complete upload, background ingestion, catalog appearance, and chunk search."""
    pdf_path = _create_synthetic_clinical_pdf(tmp_path)
    book_title = f"Testbook of Cardiology {int(time.time())}"
    book_specialty = "Cardiovascular Medicine"

    with open(pdf_path, "rb") as f:
        files = {"file": ("synthetic_cardiology.pdf", f, "application/pdf")}
        data = {"title": book_title, "specialty": book_specialty}
        res = client.post("/api/books/upload", data=data, files=files)

    assert res.status_code == 202
    body = res.json()
    job_id = body["job_id"]
    assert body["status"] == "queued"
    assert body["title"] == book_title

    # Poll until background job completes (should take < 2 seconds for 3 pages)
    max_wait = 15.0
    start = time.time()
    final_status = None

    while time.time() - start < max_wait:
        poll_res = client.get(f"/api/books/ingestion/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        if poll_data["status"] in ("completed", "failed"):
            final_status = poll_data
            break
        time.sleep(0.3)

    assert final_status is not None, "Ingestion job timed out"
    assert final_status["status"] == "completed", f"Job failed: {final_status.get('user_error_message')}"
    assert final_status["progress_percent"] == 100
    assert final_status["sections_count"] >= 3
    assert final_status["chunks_count"] >= 2

    # 1. Verify book appears in GET /api/books
    books_res = client.get("/api/books")
    assert books_res.status_code == 200
    all_books = books_res.json()["books"]
    matched_book = next((b for b in all_books if b["title"] == book_title), None)
    assert matched_book is not None, f"Uploaded book {book_title} not found in /api/books"
    assert matched_book["total_pages"] == 3

    # 2. Verify book appears in GET /api/user/library global catalog
    lib_res = client.get("/api/user/library")
    assert lib_res.status_code == 200
    catalog = lib_res.json()["global_catalog"]
    matched_catalog_book = next((b for b in catalog if b["title"] == book_title), None)
    assert matched_catalog_book is not None
    assert matched_catalog_book["specialty"] == book_specialty

    # 3. Verify chunk search finds the ingested content
    hits = search_chunks("physiologic pacemaker healthy heart", book_slug=matched_book["slug"], limit=3)
    assert len(hits) > 0
    assert "pacemaker" in hits[0]["text"].lower()


def test_scanned_pdf_failure_classification(tmp_path: Path):
    """Verifies that an image-only/textless PDF triggers user-friendly Scanned notice."""
    blank_pdf = tmp_path / "blank_scanned.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(blank_pdf))
    doc.close()

    job_id = "test-scanned-job"
    create_job(job_id=job_id, title="Blank Scanned Book", specialty="Radiology", book_slug="blank_scanned")
    res = run_ingestion_pipeline(job_id, blank_pdf, "Blank Scanned Book", "Radiology")

    assert res.status == "failed"
    assert "scanned document without an embedded digital text layer" in res.user_error_message
    assert "technical team has been notified" in res.user_error_message
