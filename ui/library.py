"""User Library and Personal Textbook Scope Persistence Service.

Manages SQLite storage for user personal textbook curation and active consultation toggles in app_users.db.
Distinguishes between:
- Global Catalog: All indexed textbooks available in the system.
- User Library (My Study Library): User's curated collection with individual consultation active switches.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from retrieval.router import BOOK_SPECIALTY_PROFILES
from retrieval.tools import list_books
from ui.auth import get_auth_db_path


@contextmanager
def _get_conn(db_path: Path | str | None = None):
    """Establishes an isolated SQLite connection with WAL mode, foreign keys, and auto-close."""
    target_path = get_auth_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_user_library_db(db_path: Path | str | None = None) -> None:
    """Initializes the user_library table in app_users.db."""
    with _get_conn(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_library (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                book_slug TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, book_slug)
            );

            CREATE INDEX IF NOT EXISTS idx_user_library_user_id ON user_library(user_id);
            """
        )


def _enrich_book_metadata(raw_book: dict[str, Any]) -> dict[str, Any]:
    """Enriches a raw book entry with specialty, clean title, and description."""
    slug = raw_book.get("slug", "")
    profile = BOOK_SPECIALTY_PROFILES.get(slug, {})
    return {
        "id": raw_book.get("id"),
        "slug": slug,
        "title": profile.get("title") or raw_book.get("title") or slug,
        "specialty": raw_book.get("specialty") or profile.get("specialty", "General Medicine"),
        "total_pages": raw_book.get("total_pages", 0),
        "description": profile.get("description", "Comprehensive indexed medical textbook."),
    }


def get_global_catalog(user_id: str | None = None) -> list[dict[str, Any]]:
    """Returns all accessible textbooks enriched with metadata, filtering private books by user."""
    books = list_books(user_id=user_id)
    return [_enrich_book_metadata(b) for b in books]


def ensure_user_library_initialized(user_id: str, db_path: Path | str | None = None) -> None:
    """Ensures the user library has initial entries from the global catalog if empty."""
    init_user_library_db(db_path)
    global_books = get_global_catalog(user_id=user_id)
    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT 1 FROM user_library WHERE user_id = ? LIMIT 1;", (user_id,)
        ).fetchone()
        if not rows:
            for b in global_books:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO user_library (user_id, book_slug, is_active)
                    VALUES (?, ?, 1);
                    """,
                    (user_id, b["slug"]),
                )


def get_user_library(user_id: str, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Retrieves user's personal curated library.

    If the user has no curated books yet, initializes their library by adding
    all currently available global textbooks with is_active = 1.
    """
    ensure_user_library_initialized(user_id, db_path)
    global_books = get_global_catalog(user_id=user_id)
    global_by_slug = {b["slug"]: b for b in global_books}

    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT book_slug, is_active, added_at
            FROM user_library
            WHERE user_id = ?
            ORDER BY added_at ASC;
            """,
            (user_id,),
        ).fetchall()

    user_books: list[dict[str, Any]] = []
    for slug, is_active, added_at in rows:
        meta = global_by_slug.get(slug, {
            "id": None,
            "slug": slug,
            "title": slug,
            "specialty": "General Medicine",
            "total_pages": 0,
            "description": "",
        })
        user_books.append({
            **meta,
            "is_active": bool(is_active),
            "added_at": str(added_at),
        })

    return user_books


def add_to_user_library(
    user_id: str,
    book_slug: str,
    is_active: bool = True,
    db_path: Path | str | None = None,
) -> bool:
    """Adds a textbook to the user's personal library."""
    ensure_user_library_initialized(user_id, db_path)
    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_library (user_id, book_slug, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, book_slug) DO UPDATE SET is_active = excluded.is_active;
            """,
            (user_id, book_slug, 1 if is_active else 0),
        )
        return cur.rowcount > 0


def remove_from_user_library(
    user_id: str,
    book_slug: str,
    db_path: Path | str | None = None,
) -> bool:
    """Removes a textbook from the user's personal library."""
    ensure_user_library_initialized(user_id, db_path)
    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_library WHERE user_id = ? AND book_slug = ?;",
            (user_id, book_slug),
        )
        return cur.rowcount > 0


def toggle_user_book_active(
    user_id: str,
    book_slug: str,
    is_active: bool | None = None,
    db_path: Path | str | None = None,
) -> bool:
    """Toggles or sets the active consultation state for a textbook in user library."""
    ensure_user_library_initialized(user_id, db_path)
    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        if is_active is None:
            cur.execute(
                """
                UPDATE user_library
                SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
                WHERE user_id = ? AND book_slug = ?;
                """,
                (user_id, book_slug),
            )
        else:
            cur.execute(
                """
                UPDATE user_library
                SET is_active = ?
                WHERE user_id = ? AND book_slug = ?;
                """,
                (1 if is_active else 0, user_id, book_slug),
            )
        return cur.rowcount > 0


def set_all_user_books_active(
    user_id: str,
    is_active: bool = True,
    db_path: Path | str | None = None,
) -> int:
    """Sets all textbooks in the user's library to active or inactive."""
    ensure_user_library_initialized(user_id, db_path)
    with _get_conn(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_library SET is_active = ? WHERE user_id = ?;",
            (1 if is_active else 0, user_id),
        )
        return cur.rowcount
