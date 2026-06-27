"""Database connection layer for the vulnerable security lab.

Provides a minimal SQLite access layer with automatic schema creation.
The database file lives at the PROJECT ROOT as ``vulnerable_app.db`` so it can
be conveniently downloaded via the (intentionally) unauthenticated
``/download/db`` endpoint.

Educational note: ``check_same_thread=False`` is used to keep the example simple
(single shared connection across threads). This is a simplification, not a
recommended production pattern.
"""

import sqlite3
from pathlib import Path

# Resolve the project root relative to this file so the path is stable
# regardless of the directory the app is launched from.
#   session.py -> db -> app -> backend -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "vulnerable_app.db"


def get_db() -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    Uses ``sqlite3.Row`` so rows support dict-style access, and
    ``check_same_thread=False`` to allow the connection to be shared.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the ``users`` table if it does not already exist.

    Idempotent: safe to call on every startup. If the database file has been
    deleted, this recreates an empty schema (the "delete file to reset"
    workflow).
    """
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email    TEXT,
                password TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
