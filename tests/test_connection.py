"""Regression tests for db/connection.py:
- init_db on a fresh DB must seed the same source weights schema.sql declares;
- _migrate on a pre-column DB must seed the SAME values (not the pre-2026 scale
  it used to write), or migrated and fresh DBs silently diverge;
- foreign keys are enforced (schema.sql declares REFERENCES but SQLite only
  honors them when the pragma is on)."""

import sqlite3

import pytest

from db import repository
from db.connection import get_connection, init_db

SCHEMA_WEIGHT_STATS = {
    "fantacalcio_online": 10,
    "fantanalisi": 25,
    "fantapazz": 25,
    "fantacalcio_it": 20,
    "pianetafanta": 10,
    "fantacalciopedia": 10,
}


def test_fresh_init_db_seeds_schema_weights(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    rows = {r["name"]: r["weight_stats"] for r in conn.execute("SELECT name, weight_stats FROM sources")}
    assert rows == SCHEMA_WEIGHT_STATS
    conn.close()


def test_migrate_on_old_db_seeds_new_schema_weights(tmp_path):
    """An old DB whose sources table predates weight_stats must end up with the
    values schema.sql declares, not the pre-2026 relative scale the migration
    was previously seeding (3/2/1.5/...)."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sources (name TEXT PRIMARY KEY, weight REAL NOT NULL DEFAULT 1)")
    conn.executemany("INSERT INTO sources (name, weight) VALUES (?, ?)", [
        ("fantacalcio_online", 45), ("fantanalisi", 35), ("fantapazz", 10),
        ("fantacalcio_it", 0), ("pianetafanta", 5), ("fantacalciopedia", 5),
    ])
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = get_connection(db_path)
    rows = {r["name"]: r["weight_stats"] for r in conn.execute("SELECT name, weight_stats FROM sources")}
    assert rows == SCHEMA_WEIGHT_STATS
    conn.close()


def test_foreign_keys_enforced(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        repository.insert_quotation(
            conn, player_id=99999, source="fantacalcio_it", scrape_date="2026-08-27",
            price_current=10, price_initial=9, status="ok",
            fantamedia=6.5, avg_rating=6.4, appearances=30,
        )
    conn.close()


def test_journal_mode_is_wal(tmp_path):
    """Readers (Streamlit) and the writer (scraping pipeline) hold the file
    open concurrently — WAL lets them proceed without blocking each other
    (TASK-020/DB5)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.close()