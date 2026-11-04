"""Integration tests for Personal Library privacy, auto-activation, and multi-tenant isolation."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from ui.app import app
from ingestion.pipeline_worker import DEFAULT_DB_PATH


@pytest.fixture
def client_a():
    return TestClient(app)


@pytest.fixture
def client_b():
    return TestClient(app)


def _create_synthetic_guideline_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "synthetic_diabetes_guideline.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 70), "Chapter 1: ADA Diabetes Standards of Care", fontsize=16)
    p1.insert_textbox(
        pymupdf.Rect(50, 90, 550, 300),
        "Level 1 hypoglycemia is defined as blood glucose less than 70 mg/dL. "
        "Level 2 hypoglycemia is serious hypoglycemia defined as blood glucose less than 54 mg/dL. "
        "Level 3 hypoglycemia is severe hypoglycemia defined by altered mental status requiring assistance.",
        fontsize=11,
    )
    doc.set_toc([[1, "Chapter 1: ADA Diabetes Standards of Care", 1]])
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_personal_library_privacy_and_isolation(tmp_path: Path, client_a: TestClient, client_b: TestClient):
    # AC: Uploaded textbook marked private must be auto-activated in owner's library,
    #     visible to owner, and completely hidden from other users.
    pdf_path = _create_synthetic_guideline_pdf(tmp_path)
    book_title = f"Private ADA Guideline {int(time.time())}"
    book_specialty = "Endocrinology"

    # User A initiates session
    res_a_init = client_a.get("/api/user/library")
    assert res_a_init.status_code == 200

    # User A uploads textbook with is_private = True
    with open(pdf_path, "rb") as f:
        files = {"file": ("ada_guidelines.pdf", f, "application/pdf")}
        data = {
            "title": book_title,
            "specialty": book_specialty,
            "is_private": "true",
        }
        res_upload = client_a.post("/api/books/upload", data=data, files=files)

    assert res_upload.status_code == 202
    body = res_upload.json()
    job_id = body["job_id"]
    book_slug = body["book_slug"]

    # Poll until completed
    max_wait = 15.0
    start = time.time()
    final_status = None
    while time.time() - start < max_wait:
        poll_res = client_a.get(f"/api/books/ingestion/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        if poll_data["status"] in ("completed", "failed"):
            final_status = poll_data
            break
        time.sleep(0.3)

    assert final_status is not None and final_status["status"] == "completed"

    try:
        # 1. User A checks their personal library: new book MUST be present and active
        lib_a = client_a.get("/api/user/library").json()
        user_a_books = lib_a["library"]
        user_a_book = next((b for b in user_a_books if b["slug"] == book_slug), None)
        assert user_a_book is not None, f"Expected {book_slug} in User A's study library"
        assert user_a_book["is_active"] is True

        # 2. User B checks their library and global catalog: private book MUST NOT appear
        res_b_init = client_b.get("/api/user/library")
        assert res_b_init.status_code == 200
        lib_b = res_b_init.json()

        # In User B's study library:
        user_b_books = lib_b["library"]
        assert not any(b["slug"] == book_slug for b in user_b_books)

        # In User B's global catalog:
        user_b_catalog = lib_b["global_catalog"]
        assert not any(b["slug"] == book_slug for b in user_b_catalog)

        # In User B's /api/books:
        books_b = client_b.get("/api/books").json()["books"]
        assert not any(b["slug"] == book_slug for b in books_b)

    finally:
        # Clean up database
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute("DELETE FROM chunks WHERE book_slug = ?;", (book_slug,))
        conn.execute("DELETE FROM sections WHERE book_slug = ?;", (book_slug,))
        conn.execute("DELETE FROM books WHERE slug = ?;", (book_slug,))
        conn.commit()
        conn.close()
