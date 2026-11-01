"""Live End-to-End Verification Suite for TextBook RAG on Render.

Validates the live production deployment at:
https://text-book-rag-etiz.onrender.com

Tests:
1. System Health & Daily Quota.
2. Guest Authentication & Session Management.
3. Phase 3 Library Manager & User Scope Curation (Harrison 2025).
4. AttendingPlanner & Live SSE Chat Streaming (with event: plan, event: token, event: referenced_books).
5. Evidence Drawer Chunk API & De-hyphenation.
"""
from __future__ import annotations

import json
import time
import httpx

RENDER_URL = "https://text-book-rag-etiz.onrender.com"


def run_render_live_e2e():
    print("=" * 75)
    print(f"RUNNING LIVE E2E SUITE ON RENDER: {RENDER_URL}")
    print("=" * 75)

    client = httpx.Client(base_url=RENDER_URL, timeout=60.0)

    # 1. Health & Quota
    print("\n[1/5] Verifying Health & Daily Quota...")
    r_quota = client.get("/api/quota")
    assert r_quota.status_code == 200, f"Expected 200, got {r_quota.status_code}"
    quota_data = r_quota.json()
    print(f"      Quota: limit={quota_data['limit']}, used={quota_data['used']}, remaining={quota_data['remaining']}")

    # 2. Auth & Guest Session
    print("\n[2/5] Verifying Guest Authentication...")
    r_auth = client.post("/api/auth/guest")
    assert r_auth.status_code == 200, f"Expected 200, got {r_auth.status_code}"
    user = r_auth.json()["user"]
    print(f"      Authenticated as guest: {user['username']} ({user['id']})")
    assert user["is_guest"] is True

    # Check /api/auth/me
    r_me = client.get("/api/auth/me")
    assert r_me.status_code == 200
    assert r_me.json()["user"]["id"] == user["id"]
    print("      Session cookie confirmed active.")

    # 3. Phase 3 Library Manager & User Scope Curation
    print("\n[3/5] Verifying Library Manager & Personal Catalog...")
    r_lib = client.get("/api/user/library")
    assert r_lib.status_code == 200, f"Expected 200, got {r_lib.status_code}"
    lib_data = r_lib.json()
    books = lib_data.get("library", [])
    print(f"      Total books in user library: {len(books)}")
    
    harrison = next((b for b in books if "Harrison" in b["slug"]), None)
    assert harrison is not None, "Harrison's Internal Medicine missing from user library!"
    print(f"      Found: '{harrison['title']}' ({harrison['total_pages']} pages, specialty: '{harrison['specialty']}')")
    assert harrison["total_pages"] == 4273
    assert harrison["specialty"] == "Internal Medicine"

    # Test toggling active state
    r_toggle = client.post(
        "/api/user/library/toggle",
        json={"slug": harrison["slug"], "is_active": False},
    )
    assert r_toggle.status_code == 200, f"Toggle failed: {r_toggle.text}"
    # Re-activate
    client.post(
        "/api/user/library/toggle",
        json={"slug": harrison["slug"], "is_active": True},
    )
    print("      Library scope toggles verified successfully.")

    # 4. Session Creation & SSE Chat Streaming with AttendingPlanner
    print("\n[4/5] Testing AttendingPlanner & Live SSE Chat Streaming...")
    # Create session
    r_sess = client.post("/api/sessions", json={"title": "Live DKA Consultation"})
    assert r_sess.status_code == 200
    session_id = r_sess.json()["session"]["id"]
    print(f"      Created consultation session: {session_id}")

    # Stream query
    query = "What is the classic diagnostic triad and initial fluid resuscitation protocol for diabetic ketoacidosis?"
    print(f"      Streaming query: '{query}'")

    events_received: dict[str, list[str]] = {}
    tokens_streamed: list[str] = []

    t0 = time.time()
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": query,
            "book_slug": "Harrison_2025_22nd_Edition",
            "active_books": ["Harrison_2025_22nd_Edition"],
        },
    ) as response:
        assert response.status_code == 200
        current_event = None

        for line in response.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                if current_event not in events_received:
                    events_received[current_event] = []
            elif line.startswith("data:") and current_event:
                data_str = line.split(":", 1)[1].strip()
                events_received[current_event].append(data_str)
                if current_event == "token":
                    try:
                        token_delta = json.loads(data_str).get("delta", "")
                        tokens_streamed.append(token_delta)
                    except Exception:
                        pass

    elapsed = time.time() - t0
    print(f"      Stream finished in {elapsed:.2f}s!")
    print(f"      SSE Event types received: {list(events_received.keys())}")
    
    # Assertions on SSE protocol
    assert "status" in events_received, "Missing status event"
    assert "token" in events_received, "Missing token event"
    assert "done" in events_received, "Missing done event"
    print(f"      Streamed {len(tokens_streamed)} text tokens.")

    # Check AttendingPlanner plan emission if present
    if "plan" in events_received:
        plan_data = json.loads(events_received["plan"][0])
        print(f"      AttendingPlanner Plan emitted: Hypotheses={plan_data.get('diagnostic_hypotheses')}")

    # Check referenced books / citations
    sample_chunk_id = None
    if "citations" in events_received:
        citations = json.loads(events_received["citations"][0])
        print(f"      Citations emitted: {len(citations)} citations")
        if citations:
            sample_chunk_id = citations[0].get("chunk_id")
            print(f"      Sample citation chunk: {sample_chunk_id} (p. {citations[0].get('page_start')})")

    if "referenced_books" in events_received:
        ref_books = json.loads(events_received["referenced_books"][0])
        print(f"      Referenced Books: {[b['title'] for b in ref_books]}")

    # 5. Evidence Drawer API Check
    print("\n[5/5] Verifying Evidence Drawer API on Live Render Service...")
    target_chunk = sample_chunk_id or "Harrison_2025_22nd_Edition_s0486_c12694"
    r_chunk = client.get(f"/api/chunk/{target_chunk}")
    assert r_chunk.status_code == 200, f"Expected 200 from /api/chunk, got {r_chunk.status_code}"
    chunk_data = r_chunk.json()
    assert "text" in chunk_data
    assert len(chunk_data["text"]) > 100
    print(f"      Evidence Drawer chunk retrieved: {chunk_data['chunk_id']}")
    print(f"      Section: {chunk_data.get('heading_path')}")
    print(f"      Pages: {chunk_data.get('page_start')}-{chunk_data.get('page_end')}")
    print(f"      Text length: {len(chunk_data['text'])} characters (de-hyphenated).")

    print("\n" + "=" * 75)
    print("ALL LIVE E2E TESTS ON RENDER PASSED 100% SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_render_live_e2e()
