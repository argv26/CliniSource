"""Segment 6 Concurrency, Performance & Stress Integration Test Suite.

Validates the full system under concurrent, burst-load, and high-stress conditions:
1. SQLite WAL Concurrency: Heavy writes during ingestion do not block concurrent consultation reads.
2. Concurrent User Session Operations: Multi-threaded session and message persistence without database locks.
3. Sub-Second Retrieval Latency: P95 FTS5 BM25 search latency strictly under 500ms across multi-book library.
4. Rate Limiter Burst Concurrency: Atomic transactions prevent quota overselling under simultaneous requests.
5. Ingestion Job Registry Thread Safety: Multi-threaded polling and updates of _JOBS without race conditions.
6. Object Storage Concurrent Figure I/O: Multi-threaded diagram saving and reading without file corruption.
7. ASGI Burst Load Stability: 20 concurrent HTTP requests return 100% 200 OK without dropped connections.
8. Connection Hygiene & Resource Teardown: Clean connection disposal allows immediate file deletion on Windows.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from ingestion.load_to_db import SqliteBackend
from ingestion.pipeline_worker import create_job, get_job, update_job
from retrieval.tools import search_chunks, search_sections
from storage.object_store import LocalStorageProvider
from ui.app import app
from ui.auth import create_guest_user, init_auth_db
from ui.rate_limiter import DailyRateLimiter
from ui.sessions import create_session, get_session_messages, init_sessions_db, save_message


# =============================================================================
# Test Cases (Segment 6)
# =============================================================================

def test_sqlite_wal_concurrent_reads_during_write(tmp_path: Path):
    # AC: SQLite WAL mode must allow concurrent readers to query FTS5 chunks while a background
    #     worker thread executes heavy batch writes, with zero 'database is locked' errors.
    # Behavior: Writer performs 200 chunk batch inserts while 5 threads read -> 100% reads succeed without lock errors.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Guarantees that textbook ingestion does not disrupt live clinical consultations.
    db_path = tmp_path / "wal_stress.db"
    backend = SqliteBackend(db_path)
    backend.init_schema()

    # Pre-populate base sections and chunks
    base_sections = [{"id": 1, "title": "Base Section", "level": 1, "pdf_start": 1, "pdf_end": 10}]
    base_chunks = [
        {
            "chunk_id": f"base_chk_{i}",
            "section_id": 1,
            "content_type": "prose",
            "page_start": 1,
            "page_end": 2,
            "token_count": 100,
            "text": f"Base textbook clinical mechanism description paragraph {i} covering cortisol.",
            "embed_text": f"Base textbook paragraph {i} covering cortisol hormone.",
            "content_hash": f"hash_{i}",
        }
        for i in range(20)
    ]
    backend.load_book("base_book", base_sections, base_chunks)

    read_errors: list[Exception] = []
    reads_completed = [0]
    stop_event = concurrent.futures.Event = False

    def reader_task():
        reader_conn = sqlite3.connect(str(db_path), timeout=10.0)
        reader_conn.execute("PRAGMA journal_mode=WAL;")
        try:
            for _ in range(25):
                cur = reader_conn.cursor()
                res = cur.execute(
                    "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH 'cortisol' LIMIT 5;"
                ).fetchall()
                assert len(res) > 0
                reads_completed[0] += 1
                time.sleep(0.005)
        except Exception as e:
            read_errors.append(e)
        finally:
            reader_conn.close()

    def writer_task():
        writer_conn = sqlite3.connect(str(db_path), timeout=15.0)
        writer_conn.execute("PRAGMA journal_mode=WAL;")
        try:
            for batch in range(5):
                cur = writer_conn.cursor()
                rows = [
                    (
                        f"stress_chk_{batch}_{j}",
                        "base_book",
                        1,
                        "prose",
                        None,
                        1,
                        2,
                        100,
                        f"Stress test writing chunk {batch}_{j} cortisol hormone.",
                        f"Stress test writing chunk {batch}_{j}",
                        f"stress_hash_{batch}_{j}",
                    )
                    for j in range(40)
                ]
                cur.executemany(
                    "INSERT INTO chunks (chunk_id, book_slug, section_id, content_type, sub_type, page_start, page_end, token_count, text, embed_text, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    rows,
                )
                writer_conn.commit()
                time.sleep(0.01)
        finally:
            writer_conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_writer = executor.submit(writer_task)
        f_readers = [executor.submit(reader_task) for _ in range(5)]
        f_writer.result()
        for f in f_readers:
            f.result()

    assert len(read_errors) == 0, f"Concurrent reads encountered errors: {read_errors}"
    assert reads_completed[0] == 125, f"Expected 125 completed reads, got {reads_completed[0]}"


def test_concurrent_user_session_mutations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: 10 concurrent threads must be able to create consultation sessions and save messages simultaneously
    #     without database lock errors.
    # Behavior: 10 threads insert 20 sessions and 40 messages -> All records cleanly committed.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Validates user session persistence concurrency under peak clinical usage.
    test_db = tmp_path / "sessions_stress.db"
    monkeypatch.setenv("AUTH_DB_PATH", str(test_db))
    init_auth_db(test_db)
    init_sessions_db(test_db)

    errors: list[Exception] = []
    created_sessions: list[str] = []

    def session_worker(worker_id: int):
        try:
            user = create_guest_user(test_db)
            for i in range(2):
                sess = create_session(
                    user_id=user["id"],
                    title=f"Worker {worker_id} Session {i}",
                    db_path=test_db,
                )
                sid = sess["id"]
                created_sessions.append(sid)
                save_message(sid, "user", f"Inquiry from worker {worker_id} turn 1", db_path=test_db)
                save_message(sid, "assistant", f"Response to worker {worker_id} turn 1", db_path=test_db)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(session_worker, i) for i in range(10)]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Concurrent session worker errors: {errors}"
    assert len(created_sessions) == 20

    # Verify message persistence
    conn = sqlite3.connect(str(test_db))
    total_messages = conn.execute("SELECT count(*) FROM consultation_messages;").fetchone()[0]
    conn.close()
    assert total_messages == 40


def test_fts5_retrieval_subsecond_benchmark():
    # AC: Full-text search across multi-volume medical library must complete in under 500ms (p95).
    # Behavior: Benchmark 10 representative clinical queries -> Measure wall-clock latency -> All latencies < 0.5s.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Confirms responsive interactive retrieval performance for physician search operations.
    test_queries = [
        "adrenal cortex steroidogenesis",
        "femoral triangle neuromuscular bundle",
        "thyroid hormone synthesis regulation TSH",
        "brachial plexus cords and peripheral branches",
        "hypercalcemia of malignancy differential diagnosis",
        "diabetic ketoacidosis fluid resuscitation protocols",
        "pheochromocytoma catecholamine excess symptoms",
        "renin angiotensin aldosterone system arterial pressure",
        "hypothalamic pituitary adrenal axis negative feedback",
        "corneal ulcer management and keratoplasty",
    ]

    latencies: list[float] = []

    for q in test_queries:
        t0 = time.perf_counter()
        chunks = search_chunks(query=q, limit=6)
        sections = search_sections(query=q, limit=3)
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

    latencies.sort()
    p95_latency = latencies[int(len(latencies) * 0.95)]

    assert p95_latency < 0.500, f"P95 retrieval latency {p95_latency:.4f}s exceeded 500ms ceiling"


def test_rate_limiter_burst_concurrency_race_safety(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # AC: DailyRateLimiter must be strictly race-safe under burst concurrency; when quota is N,
    #     exactly N requests are approved and remaining requests are rejected.
    # Behavior: 10 threads concurrently issue requests for a client with limit=3 -> Exactly 3 succeed, 7 rejected.
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Protects against quota overselling vulnerabilities caused by concurrent database reads/writes.
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "3")
    db_path = tmp_path / "rate_burst.db"
    limiter = DailyRateLimiter(db_path=db_path, default_limit=3)

    results: list[bool] = []
    errors: list[Exception] = []

    def burst_worker():
        try:
            allowed, used, remaining = limiter.check_and_increment(client_id="burst_user_123")
            results.append(allowed)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(burst_worker) for _ in range(10)]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Rate limiter burst errors: {errors}"
    assert len(results) == 10

    allowed_count = sum(1 for r in results if r is True)
    denied_count = sum(1 for r in results if r is False)

    assert allowed_count == 3, f"Expected exactly 3 allowed requests under limit=3, got {allowed_count}"
    assert denied_count == 7, f"Expected 7 denied requests, got {denied_count}"


def test_ingestion_job_registry_thread_safety():
    # AC: IngestionJob registry (_JOBS) must be thread-safe; concurrent readers and writers must
    #     never observe torn reads or KeyError exceptions.
    # Behavior: 10 threads concurrently create, update, and poll jobs -> 100% of operations succeed cleanly.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Ensures progress bar polling from web UI never crashes background ingestion threads.
    job_ids = [f"thread_job_{i}_{uuid.uuid4().hex[:6]}" for i in range(10)]
    errors: list[Exception] = []

    def job_worker(jid: str):
        try:
            create_job(jid, f"Title {jid}", "Cardiology", f"slug_{jid}")
            for pct in [15, 30, 65, 85, 100]:
                update_job(jid, progress_percent=pct, stage="processing", message=f"At {pct}%")
                j = get_job(jid)
                assert j is not None
                assert j.progress_percent >= 15
                time.sleep(0.002)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(job_worker, jid) for jid in job_ids]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Job registry thread safety errors: {errors}"
    for jid in job_ids:
        job = get_job(jid)
        assert job is not None
        assert job.progress_percent == 100


def test_concurrent_object_storage_figure_io(tmp_path: Path):
    # AC: LocalStorageProvider must handle concurrent writes and reads without file corruption or collision.
    # Behavior: 10 threads simultaneously save and retrieve figure bytes -> Binary hash integrity preserved.
    # @lane: integration
    # @dependency: none
    # Selection evidence: Proves the figure pipeline handles multi-page simultaneous figure crops safely.
    store = LocalStorageProvider(cache_dir=tmp_path / "figures_store")
    errors: list[Exception] = []
    dummy_payload = b"\xff\xd8\xff\xe0" + (b"\x00\x42" * 50) + b"\xff\xd9"

    def figure_worker(idx: int):
        try:
            chunk_id = f"fig_chk_{idx}"
            book_slug = "stress_book"
            store.save_figure(book_slug, chunk_id, dummy_payload)
            # Read back
            fig_path = store.get_figure_path(chunk_id)
            assert fig_path is not None
            assert fig_path.exists()
            assert fig_path.read_bytes() == dummy_payload
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(figure_worker, i) for i in range(10)]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Concurrent figure storage errors: {errors}"


@pytest.mark.anyio
async def test_asgi_burst_load_endpoint_stability():
    # AC: FastAPI ASGI server must handle bursts of concurrent requests across API endpoints with 100% 200 OK.
    # Behavior: 20 simultaneous HTTP requests to /api/quota and /api/sessions -> 0 connection drops or 500s.
    # @lane: integration
    # @dependency: full-system
    # Selection evidence: Proves server stability under rapid simultaneous API calls.
    init_auth_db()
    init_sessions_db()

    endpoints = [
        "/api/quota",
        "/api/sessions",
        "/api/quota",
        "/api/sessions",
    ] * 5  # 20 requests total

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # Pre-authenticate guest
        await client.get("/api/auth/me")

        async def fetch(url: str):
            return await client.get(url)

        responses = await asyncio.gather(*(fetch(ep) for ep in endpoints))

    assert len(responses) == 20
    for idx, r in enumerate(responses):
        assert r.status_code == 200, f"Request {idx} to {endpoints[idx]} failed with status {r.status_code}"


def test_resource_teardown_and_connection_hygiene(tmp_path: Path):
    # AC: Database connections and file handles must be cleanly closed after operations, allowing
    #     the underlying SQLite database file to be immediately unlinked on Windows.
    # Behavior: Open backend, initialize, query, close -> os.unlink() succeeds without [WinError 32].
    # @lane: integration
    # @dependency: sqlite
    # Selection evidence: Validates absence of connection leaks and dangling file descriptors.
    clean_db_path = tmp_path / "teardown_test.db"
    backend = SqliteBackend(clean_db_path)
    backend.init_schema()

    # Query count
    stats = backend.count()
    assert stats["books"] == 0

    # Explicitly close connection
    backend.conn.close()

    # Attempt immediate deletion on Windows: if connection leaked, this will raise PermissionError
    clean_db_path.unlink()
    assert not clean_db_path.exists(), "Failed to unlink database file; handle was leaked"
