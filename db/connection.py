import os
import sqlite3

from matching.player_matcher import normalize_name, normalize_team


def get_connection(db_path: str) -> sqlite3.Connection:
    # Streamlit (reads) and the scraping pipeline (writes) can legitimately
    # hold the file open at the same time; without a busy timeout, sqlite3
    # raises "database is locked" immediately instead of waiting its turn.
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # schema.sql declares 13 REFERENCES players(id) but SQLite only enforces
    # them when the pragma is enabled per-connection — it defaults to OFF, so
    # the foreign keys were purely declarative. Enabled here so a stale/missing
    # parent player can never silently orphan child rows (audit DB check: no
    # orphans found in any table, so turning this on breaks nothing).
    conn.execute("PRAGMA foreign_keys = ON")
    # Streamlit (reads) and the scraping pipeline (writes) hold the file open
    # concurrently (see the timeout above) — WAL lets readers and the writer
    # proceed without blocking each other, instead of DELETE mode's exclusive
    # write lock (TASK-020/DB5).
    conn.execute("PRAGMA journal_mode = WAL")
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
        # Must stay byte-for-byte consistent with the INSERT in schema.sql,
        # or a DB migrated from an old version silently diverges from a fresh
        # one (audit: old values 3/2/1.5 were the previous decade's scale).
        conn.executemany(
            "UPDATE sources SET weight_stats = ? WHERE name = ?",
            [(10, "fantacalcio_online"), (25, "fantanalisi"), (25, "fantapazz"),
             (20, "fantacalcio_it"), (10, "pianetafanta"), (10, "fantacalciopedia")],
        )
    if _table_exists(conn, "player_source_matches") and not _column_exists(
        conn, "player_source_matches", "review_status",
    ):
        conn.execute("ALTER TABLE player_source_matches ADD COLUMN review_status TEXT")
    if _table_exists(conn, "players"):
        if not _column_exists(conn, "players", "identity_key"):
            conn.execute("ALTER TABLE players ADD COLUMN identity_key TEXT")
        # One-off backfill (TASK-007/P0-007): verified 0 collisions on the
        # real DB (803 players), so this is a plain backfill, not a merge —
        # every row still ends up with a distinct identity_key. Only rows
        # missing one are touched, so this is a no-op on repeat runs.
        rows = conn.execute(
            "SELECT id, canonical_name, team FROM players WHERE identity_key IS NULL"
        ).fetchall()
        conn.executemany(
            "UPDATE players SET identity_key = ? WHERE id = ?",
            [
                (f"{normalize_name(row[1])}|{normalize_team(row[2])}", row[0])
                for row in rows
            ],
        )
    if _table_exists(conn, "quotations"):
        # SQLite can't add a CHECK constraint to an existing table without a
        # full rebuild, so the schema.sql constraint only protects brand-new
        # DBs — this backfill is what actually cleans up rows already
        # written before the scraper fix (P0-003): 0 was never a real
        # fantamedia, just how the source spells "no data yet".
        conn.execute("UPDATE quotations SET fantamedia = NULL WHERE fantamedia = 0")
        # Same story for idempotency (TASK-006/P1-016): insert_quotation had
        # no ON CONFLICT guard until now, so a DB written before this fix has
        # real duplicate rows for the same (player_id, source, scrape_date)
        # — confirmed on data/fantacalcio.db: 9327 stored rows for ~3509
        # distinct triples. schema.sql's UNIQUE index below would fail to
        # create on top of those duplicates, so dedupe first (keep the
        # highest id — the most recently written row — per triple).
        conn.execute(
            "DELETE FROM quotations WHERE id NOT IN ("
            "SELECT MAX(id) FROM quotations GROUP BY player_id, source, scrape_date)"
        )
    if _table_exists(conn, "my_roster"):
        # Same idempotency story as quotations above, for P1-017: without a
        # UNIQUE(player_id), a double-submitted "add to roster" form (or a
        # re-add after a typo) silently double-counted that player in
        # budget/slot math instead of updating the existing entry. Dedupe
        # first (keep the highest id) so schema.sql's UNIQUE index can be
        # created on top of a DB written before this fix.
        conn.execute(
            "DELETE FROM my_roster WHERE id NOT IN ("
            "SELECT MAX(id) FROM my_roster GROUP BY player_id)"
        )
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
