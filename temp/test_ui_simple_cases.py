"""Automated Local UI & User Flow Test Runner on Simple Cases.

Tests the FastAPI backend, serving of UI front-end assets, authentication,
consultation sessions, textbook scope management, and chat streaming.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Setup project root in sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from ui.app import app
from ui.auth import init_auth_db
from ui.sessions import init_sessions_db


results = []


def record_result(name: str, passed: bool, duration_ms: float, details: str = ""):
    status_str = "PASS" if passed else "FAIL"
    results.append({
        "name": name,
        "status": status_str,
        "duration_ms": duration_ms,
        "details": details,
    })
    print(f"[{status_str}] {name} ({duration_ms:.1f}ms) {details}", flush=True)


async def test_case_1_ui_shell_and_assets(client: httpx.AsyncClient):
    """Case 1: Test index page HTML and static assets (styles.css, app.js)."""
    t0 = time.perf_counter()
    
    # 1.1 Index HTML
    res = await client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text
    assert "<title>" in html, "Missing <title> tag"
    assert 'id="messages-container"' in html, "Missing #messages-container"
    assert 'id="chat-input"' in html, "Missing #chat-input"
    assert 'id="btn-send"' in html, "Missing #btn-send"
    assert 'id="evidence-drawer"' in html, "Missing #evidence-drawer"
    assert 'id="library-list"' in html, "Missing #library-list"
    assert 'id="btn-select-all-books"' in html, "Missing #btn-select-all-books"
    assert 'id="scope-warning-toast"' in html, "Missing #scope-warning-toast"

    # 1.2 Styles CSS
    css_res = await client.get("/static/styles.css")
    assert css_res.status_code == 200, f"Expected 200 for styles.css, got {css_res.status_code}"
    assert len(css_res.text) > 500, "styles.css seems too small or empty"

    # 1.3 App JS
    js_res = await client.get("/static/app.js")
    assert js_res.status_code == 200, f"Expected 200 for app.js, got {js_res.status_code}"
    assert "handleToggleBook" in js_res.text, "app.js missing handleToggleBook"
    assert "submitQuery" in js_res.text, "app.js missing submitQuery"

    duration = (time.perf_counter() - t0) * 1000
    record_result("Case 1: UI Shell & Static Assets Delivery", True, duration, "HTML DOM, CSS, and JS verified")


async def test_case_2_auth_flows(client: httpx.AsyncClient):
    """Case 2: Test Guest Creation, User Signup, Login, and Auth Check."""
    t0 = time.perf_counter()

    # 2.1 Initially unauthenticated
    me_initial = await client.get("/api/auth/me")
    assert me_initial.status_code == 200
    assert me_initial.json().get("user") is None

    # 2.2 Guest session creation via POST /api/auth/guest
    guest_res = await client.post("/api/auth/guest")
    assert guest_res.status_code == 200
    guest_payload = guest_res.json()
    assert guest_payload["user"].get("is_guest") is True

    # 2.3 Verify GET /api/auth/me reflects the active guest user
    me_guest = await client.get("/api/auth/me")
    assert me_guest.status_code == 200
    assert me_guest.json()["user"].get("is_guest") is True

    # 2.4 New user signup
    timestamp = int(time.time() * 1000)
    username = f"uitest_{timestamp}"
    password = "SecurePassword123!"

    signup_res = await client.post("/api/auth/signup", json={"username": username, "password": password})
    assert signup_res.status_code == 201, f"Signup failed: {signup_res.text}"
    signup_data = signup_res.json()
    assert signup_data["user"]["username"] == username

    # 2.5 Check me as logged-in registered user
    me_user = await client.get("/api/auth/me")
    assert me_user.status_code == 200
    user_info = me_user.json()["user"]
    assert user_info.get("username") == username
    assert user_info.get("is_guest") is False

    # 2.6 User login with valid credentials
    login_res = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["user"]["username"] == username

    # 2.7 User login with invalid credentials should fail
    bad_login = await client.post("/api/auth/login", json={"username": username, "password": "WrongPassword!"})
    assert bad_login.status_code == 401

    duration = (time.perf_counter() - t0) * 1000
    record_result("Case 2: Authentication & Guest Session Flow", True, duration, f"Created guest, registered & authenticated {username}")


async def test_case_3_textbook_catalogue(client: httpx.AsyncClient):
    """Case 3: Verify Textbook catalogue endpoint for UI library toggles."""
    t0 = time.perf_counter()

    res = await client.get("/api/books")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert "books" in data, "Response missing 'books' key"
    books = data["books"]
    assert isinstance(books, list)

    duration = (time.perf_counter() - t0) * 1000
    record_result("Case 3: Textbook Catalogue Scope Loading", True, duration, f"Found {len(books)} indexed book(s)")


async def test_case_4_session_management(client: httpx.AsyncClient):
    """Case 4: Consultation session CRUD (create, list, update title, delete)."""
    t0 = time.perf_counter()

    # 4.1 Create new session
    create_res = await client.post("/api/sessions", json={"title": "UI Test Consultation"})
    assert create_res.status_code == 200, f"Create session failed: {create_res.text}"
    created_sess = create_res.json()["session"]
    session_id = created_sess["id"]
    assert created_sess["title"] == "UI Test Consultation"

    # 4.2 List sessions
    list_res = await client.get("/api/sessions")
    assert list_res.status_code == 200
    sessions_list = list_res.json()["sessions"]
    matching = [s for s in sessions_list if s["id"] == session_id]
    assert len(matching) > 0, "Created session not found in list"

    # 4.3 Update session title
    patch_res = await client.patch(f"/api/sessions/{session_id}", json={"title": "Renamed Consultation"})
    assert patch_res.status_code == 200
    assert patch_res.json()["session"]["title"] == "Renamed Consultation"

    # 4.4 Get session details
    get_res = await client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["session"]["title"] == "Renamed Consultation"

    # 4.5 Delete session
    del_res = await client.delete(f"/api/sessions/{session_id}")
    assert del_res.status_code == 200

    # 4.6 Verify deleted session is gone
    get_del_res = await client.get(f"/api/sessions/{session_id}")
    assert get_del_res.status_code == 404

    duration = (time.perf_counter() - t0) * 1000
    record_result("Case 4: Consultation Session Management CRUD", True, duration, f"Created, updated & deleted {session_id[:8]}")


async def test_case_5_chat_simple_turn(client: httpx.AsyncClient):
    """Case 5: Simple Chat turn with SSE Streaming endpoint."""
    t0 = time.perf_counter()
    session_id = f"simple_chat_{int(time.time() * 1000)}"

    # Check quota endpoint first
    quota_res = await client.get("/api/quota")
    assert quota_res.status_code == 200
    quota_data = quota_res.json()
    assert "remaining" in quota_data and "used" in quota_data

    # Send a simple conversational query via SSE stream
    payload = {
        "session_id": session_id,
        "message": "hello",
        "active_books": [],
    }

    events = []
    tokens = []

    async with client.stream("POST", "/api/chat/stream", json=payload, timeout=60.0) as stream_res:
        assert stream_res.status_code == 200, f"Expected 200, got {stream_res.status_code}"
        async for raw_line in stream_res.aiter_lines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.replace("event:", "").strip()
                events.append(current_event)
            elif line.startswith("data:"):
                try:
                    data = json.loads(line.replace("data:", "").strip())
                    if "delta" in data and data["delta"]:
                        tokens.append(data["delta"])
                    elif "reply" in data and data["reply"]:
                        tokens.append(data["reply"])
                except Exception:
                    pass

    # Verify session history was saved in database
    sess_res = await client.get(f"/api/sessions/{session_id}")
    assert sess_res.status_code == 200
    sess_body = sess_res.json()
    messages = sess_body.get("messages", [])
    assert len(messages) >= 2, f"Expected at least user and assistant messages, got {len(messages)}"
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"

    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "Case 5: Simple Chat & Streaming SSE Interaction",
        True,
        duration,
        f"Streamed {len(tokens)} tokens, saved {len(messages)} messages to DB"
    )


async def test_case_6_evidence_drawer_and_figures(client: httpx.AsyncClient):
    """Case 6: Evidence Drawer excerpt retrieval and diagram lightbox image."""
    t0 = time.perf_counter()
    chunk_id = "anatomy-and-physiology-2e_-_WEB_s0003_c001"

    # 6.1 Valid chunk fetch for Evidence Drawer
    chunk_res = await client.get(f"/api/chunk/{chunk_id}")
    assert chunk_res.status_code == 200, f"Expected 200, got {chunk_res.status_code}"
    chunk_data = chunk_res.json()
    assert "text" in chunk_data and len(chunk_data["text"]) > 0

    # 6.2 Valid figure image endpoint for Lightbox preview
    fig_res = await client.get(f"/api/figure/{chunk_id}/image")
    assert fig_res.status_code == 200, f"Expected 200 for figure, got {fig_res.status_code}"
    assert fig_res.headers.get("content-type") == "image/jpeg"
    assert len(fig_res.content) > 1000

    # 6.3 404 on nonexistent chunk
    bad_res = await client.get("/api/chunk/non_existent_chunk_99999")
    assert bad_res.status_code == 404

    duration = (time.perf_counter() - t0) * 1000
    record_result(
        "Case 6: Evidence Drawer & Diagram Lightbox",
        True,
        duration,
        f"Fetched chunk {chunk_id} ({len(chunk_data['text'])} chars) and JPEG diagram ({len(fig_res.content)} bytes)"
    )


async def main():
    print("=" * 70, flush=True)
    print("STARTING LOCAL UI TEST ON SIMPLE CASES", flush=True)
    print("=" * 70, flush=True)

    init_auth_db()
    init_sessions_db()

    # Use persistent cookie jar across calls
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=True,
    ) as client:
        try:
            await test_case_1_ui_shell_and_assets(client)
            await test_case_2_auth_flows(client)
            await test_case_3_textbook_catalogue(client)
            await test_case_4_session_management(client)
            await test_case_5_chat_simple_turn(client)
            await test_case_6_evidence_drawer_and_figures(client)
        except Exception as e:
            import traceback
            traceback.print_exc()
            record_result("Test Execution Encountered Error", False, 0.0, str(e))

    print("\n" + "=" * 70, flush=True)
    print("TEST SUMMARY REPORT", flush=True)
    print("=" * 70, flush=True)
    all_passed = all(r["status"] == "PASS" for r in results)
    for r in results:
        status_symbol = "[PASS]" if r["status"] == "PASS" else "[FAIL]"
        print(f"{status_symbol} {r['name']:<48} | {r['duration_ms']:>8.1f} ms | {r['details']}")
    print("-" * 70, flush=True)
    print(f"Total: {len(results)} | Passed: {sum(1 for r in results if r['status'] == 'PASS')} | Failed: {sum(1 for r in results if r['status'] == 'FAIL')}")
    print("=" * 70, flush=True)
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
