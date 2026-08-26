import sqlite3
import os


def get_connection(db_path: str) -> sqlite3.Connection:
    # Streamlit (reads) and the scraping pipeline (writes) can legitimately
    # hold the file open at the same time; without a busy timeout, sqlite3
    # raises "database is locked" immediately instead of waiting its turn.
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _migrate(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS in schema.sql never adds a column to a
    table that already exists from a previous version — new columns need an
    explicit, idempotent ALTER TABLE here instead. Must run *before*
    schema.sql's own INSERT statements reference the new column, and only
    against tables that already exist (a brand-new DB gets the column for
    free from CREATE TABLE)."""
    if _table_exists(conn, "sources") and not _column_exists(conn, "sources", "weight_stats"):
        conn.execute("ALTER TABLE sources ADD COLUMN weight_stats REAL NOT NULL DEFAULT 1")
        # ADD COLUMN ... DEFAULT 1 leaves every pre-existing source at 1,
        # wiping out the meaningful stats weights schema.sql would have set
        # on a fresh DB (INSERT OR IGNORE skips rows that already exist) —
        # seed the same values here, once, for rows already in the table.
        conn.executemany(
            "UPDATE sources SET weight_stats = ? WHERE name = ?",
            [(3, "fantacalcio_it"), (2, "fantacalciopedia"), (1.5, "fantapazz"),
             (1.5, "pianetafanta"), (1, "fantacalcio_online"), (1, "fantanalisi")],
        )
    if _table_exists(conn, "player_source_matches") and not _column_exists(
        conn, "player_source_matches", "review_status",
    ):
        conn.execute("ALTER TABLE player_source_matches ADD COLUMN review_status TEXT")
    conn.commit()


def init_db(db_path: str) -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection(db_path)
    _migrate(conn)
    conn.executescript(schema)
    conn.commit()
    conn.close()
