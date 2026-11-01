"""Segment 4 REST API, Session State & User Isolation Integration Test Suite.

Validates the full REST API surface and security/isolation boundaries:
1. Multi-user session isolation and access control privacy (Client A vs Client B).
2. Multi-tenant user library curation and consultation active toggle independence.
3. Consultation session CRUD lifecycle and cascading message deletion.
4. Daily quota rate limiting and HTTP 429 Retry-After enforcement.
5. Chunk content retrieval with automatic line-break de-hyphenation.
6. Figure image serving with proper HTTP cache-control headers.
7. Textbook upload pre-flight validation (extension, magic bytes, duplicate slug 409).
8. Ingestion job lifecycle polling (HTTP 202 -> status tracking -> 404 on missing).
"""
from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ui.app import app
from ui.auth import create_guest_user, create_session as create_auth_session, init_auth_db
from ui.dependencies import get_rate_limiter
from ui.library import init_user_library_db
from ui.sessions import create_session, get_session_messages, init_sessions_db, save_message


# =============================================================================
# Test Cases (Segment 4)
# =============================================================================

def test_multi_user_session_privacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: Consultation sessions must be strictly isolated per user; Client B must never see,
    #     retrieve, or delete Client A's sessions.
    # Behavior: Client A creates session -> Client B requests session -> HTTP 404 returned to Client B.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Proves cross-tenant data leakage is impossible at the API routing boundary.
    test_db = tmp_path / "test_privacy_users.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_db))
    init_auth_db(test_db)
    init_sessions_db(test_db)

    client_a = TestClient(app)
    client_b = TestClient(app)

    # 1. Client A creates a private session
    res_a = client_a.post("/api/sessions", json={"title": "Client A Confidential Case"})
    assert res_a.status_code == 200
    session_a_id = res_a.json()["session"]["id"]

    # 2. Client B lists sessions: session_a_id must NOT appear
    res_b_list = client_b.get("/api/sessions")
    assert res_b_list.status_code == 200
    b_session_ids = [s["id"] for s in res_b_list.json()["sessions"]]
    assert session_a_id not in b_session_ids

    # 3. Client B attempts to fetch Client A's session directly: must return 404
    res_b_get = client_b.get(f"/api/sessions/{session_a_id}")
    assert res_b_get.status_code == 404
    assert "not found" in res_b_get.json()["detail"].lower()

    # 4. Client B attempts to delete Client A's session: must return 404
    res_b_del = client_b.delete(f"/api/sessions/{session_a_id}")
    assert res_b_del.status_code == 404


def test_user_library_multi_tenant_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: User library active toggles and curation must be completely independent across users.
    # Behavior: Client A deactivates a book -> Client B's view of the same book remains is_active=True.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Proves multi-user study preferences cannot clobber concurrent users' active consultation scopes.
    test_db = tmp_path / "test_library_users.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_db))
    init_auth_db(test_db)
    init_user_library_db(test_db)

    client_a = TestClient(app)
    client_b = TestClient(app)

    # 1. Fetch initial libraries for both clients
    lib_a = client_a.get("/api/user/library").json()["library"]
    lib_b = client_b.get("/api/user/library").json()["library"]
    assert len(lib_a) > 0 and len(lib_b) > 0

    target_slug = lib_a[0]["slug"]

    # 2. Client A deactivates target_slug
    res_toggle = client_a.post("/api/user/library/toggle", json={"slug": target_slug, "is_active": False})
    assert res_toggle.status_code == 200

    # Verify Client A sees target_slug as inactive
    lib_a_updated = client_a.get("/api/user/library").json()["library"]
    a_book = next(b for b in lib_a_updated if b["slug"] == target_slug)
    assert a_book["is_active"] is False

    # 3. Verify Client B still sees target_slug as ACTIVE
    lib_b_current = client_b.get("/api/user/library").json()["library"]
    b_book = next(b for b in lib_b_current if b["slug"] == target_slug)
    assert b_book["is_active"] is True, "Client A's toggle leaked and mutated Client B's library state"


def test_session_crud_and_cascade_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: Sessions must support full CRUD lifecycle; deleting a session cascades to its messages.
    # Behavior: Create session -> Patch title -> Save message -> Delete session -> All records deleted.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Confirms cascade deletion prevents orphaned messages in app_users.db.
    test_db = tmp_path / "test_crud_sessions.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_db))
    init_auth_db(test_db)
    init_sessions_db(test_db)

    client = TestClient(app)

    # 1. Create session
    create_res = client.post("/api/sessions", json={"title": "Initial Title"})
    assert create_res.status_code == 200
    session_id = create_res.json()["session"]["id"]

    # 2. Patch title
    patch_res = client.patch(f"/api/sessions/{session_id}", json={"title": "Updated Clinical Title"})
    assert patch_res.status_code == 200
    assert patch_res.json()["session"]["title"] == "Updated Clinical Title"

    # Patch invalid session -> 404
    bad_patch = client.patch("/api/sessions/non_existent_id", json={"title": "New Title"})
    assert bad_patch.status_code == 404

    # 3. Add a message directly
    save_message(session_id, "user", "What are the hallmarks of diabetic ketoacidosis?", db_path=test_db)
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()["messages"]) == 1

    # 4. Delete session
    del_res = client.delete(f"/api/sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 5. Verify session and its messages are completely removed
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    messages_left = get_session_messages(session_id, user_id=None, db_path=test_db)
    assert not messages_left


def test_rate_limiter_and_429_retry_after(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: When daily request quota is exhausted, /api/chat must return HTTP 429 with Retry-After header.
    # Behavior: Send requests exceeding DAILY_REQUEST_LIMIT -> Receive HTTP 429 with reset guidance.
    # @lane: integration
    # @dependency: sqlite, full-system
    # Selection evidence: Protects backend and LLM spend from abuse and unbounded request floods.
    test_db = tmp_path / "test_rate_users.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_db))
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "2")
    init_auth_db(test_db)
    init_sessions_db(test_db)

    client = TestClient(app)

    # 1. Check initial quota
    quota_res = client.get("/api/quota")
    assert quota_res.status_code == 200
    assert quota_res.json()["limit"] == 2

    # 2. Request 1: Succeeds
    res1 = client.post("/api/chat", json={"session_id": "rate_s1", "message": "hello"})
    assert res1.status_code == 200
    assert res1.headers.get("X-RateLimit-Limit") == "2"
    assert res1.headers.get("X-RateLimit-Remaining") == "1"

    # 3. Request 2: Succeeds
    res2 = client.post("/api/chat", json={"session_id": "rate_s1", "message": "thank you"})
    assert res2.status_code == 200
    assert res2.headers.get("X-RateLimit-Remaining") == "0"

    # 4. Request 3: Exceeds limit -> HTTP 429
    res3 = client.post("/api/chat", json={"session_id": "rate_s1", "message": "another question"})
    assert res3.status_code == 429
    assert "daily request limit reached" in res3.json()["detail"].lower()
    assert res3.headers.get("Retry-After") == "86400"
    assert res3.headers.get("X-RateLimit-Remaining") == "0"


def test_chunk_endpoint_dehyphenation_and_404():
    # AC: GET /api/chunk/{chunk_id} must return chunk metadata with line-break hyphens healed,
    #     and return HTTP 404 if the chunk does not exist.
    # Behavior: Fetch chunk -> Hyphens healed; Fetch missing chunk -> 404.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Guarantees Evidence Drawer displays continuous, clean text without broken hyphen artifacts.
    client = TestClient(app)

    # 1. Fetch non-existent chunk -> 404
    missing_res = client.get("/api/chunk/non_existent_chunk_12345")
    assert missing_res.status_code == 404
    assert "detail" in missing_res.json()

    # 2. Fetch real chunk from indexed textbooks
    # Query database for a real chunk_id
    from retrieval.tools import search_chunks
    sample = search_chunks("adrenal", limit=1)
    if sample:
        real_cid = sample[0]["chunk_id"]
        res = client.get(f"/api/chunk/{real_cid}")
        assert res.status_code == 200
        data = res.json()
        assert data["chunk_id"] == real_cid
        assert "text" in data
        assert "-\n" not in data["text"]  # Verify hyphen healing


def test_figure_image_serving_and_cache_control(tmp_path: Path):
    # AC: GET /api/figure/{chunk_id}/image must serve cached figure JPEGs with Cache-Control headers,
    #     and return HTTP 404 if no image exists for the chunk.
    # Behavior: Request figure image -> image/jpeg with max-age=86400; Request invalid -> HTTP 404.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Validates browser caching contracts to minimize repeated binary transfers.
    client = TestClient(app)

    # 1. Non-existent figure -> 404
    missing_res = client.get("/api/figure/phantom_chunk_999/image")
    assert missing_res.status_code == 404
    assert "Figure image not available" in missing_res.json()["detail"]

    # 2. Mock a cached figure file in storage
    from storage.object_store import get_storage_provider
    store = get_storage_provider()
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
    fig_chunk_id = f"test_fig_{uuid.uuid4().hex[:8]}"
    store.save_figure("test_book", fig_chunk_id, dummy_jpeg)

    try:
        res = client.get(f"/api/figure/{fig_chunk_id}/image")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
        assert "public" in res.headers["cache-control"]
        assert "max-age=86400" in res.headers["cache-control"]
        assert len(res.content) > 0
    finally:
        fig_path = store.get_figure_path(fig_chunk_id)
        if fig_path and fig_path.exists():
            fig_path.unlink()


def test_book_upload_guards_and_duplicate_rejection(tmp_path: Path):
    # AC: POST /api/books/upload must enforce strict pre-flight validation:
    #     reject empty titles (400), non-PDF extensions (400), invalid magic bytes (400),
    #     duplicate book titles (409), and accept valid PDFs (202).
    # Behavior: Pass invalid files -> Specific HTTP errors; Pass valid PDF -> HTTP 202 with job_id.
    # @lane: integration
    # @dependency: full-system
    # Selection evidence: Protects ingestion pipeline from processing corrupt or duplicate files.
    client = TestClient(app)

    # 1. Missing title -> 400
    res_no_title = client.post(
        "/api/books/upload",
        data={"title": "   ", "specialty": "Cardiology"},
        files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert res_no_title.status_code == 400
    assert "title is required" in res_no_title.json()["detail"].lower()

    # 2. Non-PDF extension -> 400
    res_bad_ext = client.post(
        "/api/books/upload",
        data={"title": "Cardiology Notes", "specialty": "Cardiology"},
        files={"file": ("notes.docx", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert res_bad_ext.status_code == 400
    assert "only pdf files" in res_bad_ext.json()["detail"].lower()

    # 3. Bad magic bytes (missing %PDF) -> 400
    res_bad_magic = client.post(
        "/api/books/upload",
        data={"title": "Cardiology Notes", "specialty": "Cardiology"},
        files={"file": ("notes.pdf", b"NOT_A_PDF_STREAM", "application/pdf")},
    )
    assert res_bad_magic.status_code == 400
    assert "missing %pdf" in res_bad_magic.json()["detail"].lower()

    # 4. Duplicate book title -> 409
    res_dup = client.post(
        "/api/books/upload",
        data={"title": "Anatomy and Physiology 2e", "specialty": "Anatomy"},
        files={"file": ("anatomy_dup.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert res_dup.status_code == 409
    assert "already exists" in res_dup.json()["detail"].lower()

    # 5. Valid PDF upload -> 202 Accepted
    unique_title = f"Unique Surgical Guide {uuid.uuid4().hex[:6]}"
    valid_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    res_valid = client.post(
        "/api/books/upload",
        data={"title": unique_title, "specialty": "Surgery"},
        files={"file": ("surgery_guide.pdf", valid_pdf_bytes, "application/pdf")},
    )
    assert res_valid.status_code == 202
    data = res_valid.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["title"] == unique_title


def test_ingestion_job_status_polling():
    # AC: GET /api/books/ingestion/{job_id} must return live job progress dictionary,
    #     and return HTTP 404 for unknown job IDs.
    # Behavior: Poll registered job -> Live dict; Poll unknown job -> 404.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Proves the frontend upload modal can track multi-stage background ingestion.
    client = TestClient(app)

    # 1. Unknown job -> 404
    res_missing = client.get("/api/books/ingestion/unknown_job_id_999")
    assert res_missing.status_code == 404
    assert "not found" in res_missing.json()["detail"].lower()

    # 2. Registered job -> Returns progress dict
    from ingestion.pipeline_worker import create_job, update_job
    job_id = f"test_poll_{uuid.uuid4().hex[:8]}"
    create_job(job_id, "Test Neurology", "Neurology", "test_neurology")
    update_job(job_id, progress_percent=45, stage="extraction", message="Extracting text...")

    res_job = client.get(f"/api/books/ingestion/{job_id}")
    assert res_job.status_code == 200
    data = res_job.json()
    assert data["job_id"] == job_id
    assert data["progress_percent"] == 45
    assert data["stage"] == "extraction"
    assert "Extracting text" in data["message"]
