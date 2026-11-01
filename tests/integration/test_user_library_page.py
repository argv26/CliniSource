"""Integration tests for User Library and Global Catalog Endpoints."""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from ui.app import app
from ui.auth import init_auth_db
from ui.library import init_user_library_db


@pytest.fixture
def test_client(tmp_path):
    """Creates a temporary test client with an isolated SQLite database."""
    test_db = tmp_path / "test_app_users.db"
    old_db = os.environ.get("AUTH_DB_PATH")
    os.environ["AUTH_DB_PATH"] = str(test_db)
    init_auth_db(test_db)
    init_user_library_db(test_db)

    with TestClient(app) as client:
        yield client

    if old_db:
        os.environ["AUTH_DB_PATH"] = old_db
    else:
        os.environ.pop("AUTH_DB_PATH", None)


def test_get_user_library_initializes_with_indexed_books(test_client):
    """First-time user receives all globally indexed books active in their personal library."""
    res = test_client.get("/api/user/library")
    assert res.status_code == 200
    data = res.json()
    assert "library" in data
    assert "global_catalog" in data
    assert data["total_active"] >= 2
    assert len(data["library"]) >= 2
    assert len(data["global_catalog"]) >= 2

    # Check structure
    first_book = data["library"][0]
    assert "slug" in first_book
    assert "title" in first_book
    assert "specialty" in first_book
    assert first_book["is_active"] is True


def test_toggle_book_active(test_client):
    """User can toggle an active book to inactive."""
    res = test_client.get("/api/user/library")
    data = res.json()
    target_slug = data["library"][0]["slug"]

    # Toggle off
    toggle_res = test_client.post("/api/user/library/toggle", json={"slug": target_slug, "is_active": False})
    assert toggle_res.status_code == 200
    t_data = toggle_res.json()
    assert t_data["success"] is True

    # Verify updated library
    verify_res = test_client.get("/api/user/library")
    v_data = verify_res.json()
    toggled = next(b for b in v_data["library"] if b["slug"] == target_slug)
    assert toggled["is_active"] is False


def test_remove_and_add_book_to_library(test_client):
    """User can remove a book from their library and add it back from the global catalog."""
    res = test_client.get("/api/user/library")
    data = res.json()
    initial_count = len(data["library"])
    target_slug = data["library"][0]["slug"]

    # Remove book
    del_res = test_client.post("/api/user/library/remove", json={"slug": target_slug})
    assert del_res.status_code == 200
    d_data = del_res.json()
    assert len(d_data["library"]) == initial_count - 1

    # Verify global catalog shows in_user_library = False
    v_res = test_client.get("/api/user/library")
    v_data = v_res.json()
    global_target = next(b for b in v_data["global_catalog"] if b["slug"] == target_slug)
    assert global_target["in_user_library"] is False

    # Add back
    add_res = test_client.post("/api/user/library/add", json={"slug": target_slug})
    assert add_res.status_code == 200
    a_data = add_res.json()
    assert len(a_data["library"]) == initial_count


def test_toggle_all_books(test_client):
    """User can toggle all books in their library active/inactive."""
    # Deactivate all
    res = test_client.post("/api/user/library/toggle-all", json={"active": False})
    assert res.status_code == 200
    data = res.json()
    assert data["total_active"] == 0

    # Reactivate all
    res_on = test_client.post("/api/user/library/toggle-all", json={"active": True})
    assert res_on.status_code == 200
    data_on = res_on.json()
    assert data_on["total_active"] == len(data_on["library"])


def test_html_contains_view_switcher_and_library_page(test_client):
    """The HTML interface includes the header view switcher tabs and the dedicated library page."""
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "tab-view-consultation" in html
    assert "tab-view-library" in html
    assert "view-consultation" in html
    assert "view-library" in html
    assert "sidebar-sessions-container" in html
    assert "sidebar-library-container" in html
    assert "sidebar-book-count-badge" in html
    assert "btn-open-full-library" in html
    assert "subpanel-my-library" in html
    assert "subpanel-global-catalog" in html
