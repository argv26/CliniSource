import sqlite3
from pathlib import Path

db_path = Path("textbook_rag.db")
auth_db_path = Path("app_users.db")

print("--- Cleaning Test Books from textbook_rag.db ---")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# Find test books
test_books = cur.execute("SELECT slug, title FROM books WHERE slug LIKE 'Testbook_of_Cardiology%';").fetchall()
print(f"Found {len(test_books)} test books to remove:")
for slug, title in test_books:
    print(f"  - {slug}")

# Delete from chunks_fts
cur.execute("DELETE FROM chunks_fts WHERE book_slug LIKE 'Testbook_of_Cardiology%';")
# Delete from chunks
cur.execute("DELETE FROM chunks WHERE book_slug LIKE 'Testbook_of_Cardiology%';")
# Delete from sections
cur.execute("DELETE FROM sections WHERE book_slug LIKE 'Testbook_of_Cardiology%';")
# Delete from books
cur.execute("DELETE FROM books WHERE slug LIKE 'Testbook_of_Cardiology%';")
conn.commit()

# VACUUM to reclaim space and compact database
cur.execute("VACUUM;")
conn.commit()

remaining_books = cur.execute("SELECT slug, title, total_pages FROM books;").fetchall()
print(f"\nRemaining legitimate books in textbook_rag.db ({len(remaining_books)}):")
for b in remaining_books:
    print(f"  * {b[0]} | {b[1]} ({b[2]} pages)")

conn.close()

# Also clean from app_users.db if present
if auth_db_path.exists():
    auth_conn = sqlite3.connect(str(auth_db_path))
    auth_cur = auth_conn.cursor()
    auth_cur.execute("DELETE FROM user_library WHERE book_slug LIKE 'Testbook_of_Cardiology%';")
    auth_conn.commit()
    auth_conn.close()
    print("\nCleaned test books from app_users.db user_library.")

print("\nDatabase cleanup completed successfully!")
