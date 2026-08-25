import sqlite3


def upsert_player(conn: sqlite3.Connection, canonical_name: str, team: str,
                   role_classic: str, role_mantra, photo_path) -> int:
    cursor = conn.execute(
        "SELECT id FROM players WHERE canonical_name = ? AND team = ?",
        (canonical_name, team),
    )
    row = cursor.fetchone()
    if row:
        conn.execute(
            "UPDATE players SET role_classic = ?, role_mantra = ?, photo_path = "
            "COALESCE(?, photo_path) WHERE id = ?",
            (role_classic, role_mantra, photo_path, row["id"]),
        )
        conn.commit()
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra, photo_path) "
        "VALUES (?, ?, ?, ?, ?)",
        (canonical_name, team, role_classic, role_mantra, photo_path),
    )
    conn.commit()
    return cursor.lastrowid


def insert_quotation(conn: sqlite3.Connection, player_id: int, source: str,
                      scrape_date: str, price_current, price_initial, status,
                      fantamedia, avg_rating, appearances) -> None:
    conn.execute(
        "INSERT INTO quotations (player_id, source, scrape_date, price_current, "
        "price_initial, status, fantamedia, avg_rating, appearances) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, source, scrape_date, price_current, price_initial, status,
         fantamedia, avg_rating, appearances),
    )
    conn.commit()


# Rows from a season-archive import (see pipeline/run_historical_prices.py)
# carry a source ending in "_storico" and a scrape_date years in the past.
# They power the "andamento quotazione" chart via get_price_history, but must
# never enter the live consensus: a 2022/23 price averaged in with today's
# quotations would silently corrupt the current price.
HISTORICAL_SOURCE_SUFFIX = "_storico"
_EXCLUDE_HISTORICAL = f" AND q.source NOT LIKE '%{HISTORICAL_SOURCE_SUFFIX}'"


def get_latest_quotations(conn: sqlite3.Connection, role_classic: str) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.role_classic = ?
          """ + _EXCLUDE_HISTORICAL + """
          AND q.id = (
              SELECT q2.id FROM quotations q2
              WHERE q2.player_id = q.player_id AND q2.source = q.source
              ORDER BY q2.scrape_date DESC, q2.id DESC
              LIMIT 1
          )
        ORDER BY p.canonical_name
        """,
        (role_classic,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_latest_quotations(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE 1=1""" + _EXCLUDE_HISTORICAL + """
          AND q.id = (
            SELECT q2.id FROM quotations q2
            WHERE q2.player_id = q.player_id AND q2.source = q.source
            ORDER BY q2.scrape_date DESC, q2.id DESC
            LIMIT 1
        )
        ORDER BY p.canonical_name
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def get_source_stats(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        """
        SELECT source, MAX(scrape_date) AS last_update, COUNT(*) AS record_count
        FROM quotations
        WHERE source NOT LIKE '%""" + HISTORICAL_SOURCE_SUFFIX + """'
        GROUP BY source
        ORDER BY source
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def get_latest_quotations_for_player(conn: sqlite3.Connection, player_id: int) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.id = ?
          """ + _EXCLUDE_HISTORICAL + """
          AND q.id = (
              SELECT q2.id FROM quotations q2
              WHERE q2.player_id = q.player_id AND q2.source = q.source
              ORDER BY q2.scrape_date DESC, q2.id DESC
              LIMIT 1
          )
        """,
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def add_roster_entry(conn: sqlite3.Connection, player_id: int, price_paid: float,
                      date_added: str) -> None:
    conn.execute(
        "INSERT INTO my_roster (player_id, price_paid, date_added) VALUES (?, ?, ?)",
        (player_id, price_paid, date_added),
    )
    conn.commit()


def get_roster(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        """
        SELECT r.id, r.player_id, r.price_paid, r.date_added,
               p.canonical_name, p.team, p.role_classic
        FROM my_roster r
        JOIN players p ON p.id = r.player_id
        ORDER BY r.date_added
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def add_opponent_pick(conn: sqlite3.Connection, player_id: int, opponent_name: str,
                       price_paid, date_added: str) -> None:
    conn.execute(
        "INSERT INTO opponent_picks (player_id, opponent_name, price_paid, date_added) "
        "VALUES (?, ?, ?, ?)",
        (player_id, opponent_name, price_paid, date_added),
    )
    conn.commit()


def remove_opponent_pick(conn: sqlite3.Connection, player_id: int) -> None:
    conn.execute("DELETE FROM opponent_picks WHERE player_id = ?", (player_id,))
    conn.commit()


def get_opponent_picks(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        """
        SELECT o.id, o.player_id, o.opponent_name, o.price_paid, o.date_added,
               p.canonical_name, p.team, p.role_classic
        FROM opponent_picks o
        JOIN players p ON p.id = o.player_id
        ORDER BY o.date_added
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def upsert_player_notes(conn: sqlite3.Connection, player_id: int, notes: str,
                         updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_notes (player_id, notes, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET notes = excluded.notes,
                                              updated_at = excluded.updated_at
        """,
        (player_id, notes, updated_at),
    )
    conn.commit()


def get_player_notes(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        "SELECT notes FROM player_notes WHERE player_id = ?", (player_id,)
    )
    row = cursor.fetchone()
    return row["notes"] if row else None


def upsert_transfermarkt_id(conn: sqlite3.Connection, player_id: int,
                             transfermarkt_id: int, updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_transfermarkt_ids (player_id, transfermarkt_id, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET transfermarkt_id = excluded.transfermarkt_id,
                                              updated_at = excluded.updated_at
        """,
        (player_id, transfermarkt_id, updated_at),
    )
    conn.commit()


def get_transfermarkt_id(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        "SELECT transfermarkt_id FROM player_transfermarkt_ids WHERE player_id = ?",
        (player_id,),
    )
    row = cursor.fetchone()
    return row["transfermarkt_id"] if row else None


def replace_player_injuries(conn: sqlite3.Connection, player_id: int, injuries: list) -> None:
    conn.execute("DELETE FROM player_injuries WHERE player_id = ?", (player_id,))
    for injury in injuries:
        conn.execute(
            """
            INSERT OR IGNORE INTO player_injuries
                (player_id, season, injury_type, date_from, date_to, days_out, matches_missed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (player_id, injury["season"], injury["injury_type"], injury["date_from"],
             injury["date_to"], injury["days_out"], injury["matches_missed"]),
        )
    conn.commit()


def clear_quotations_for_source_and_date(conn: sqlite3.Connection, source: str,
                                          scrape_date: str) -> None:
    """Used before a historical-season import so re-running it is idempotent
    instead of duplicating rows for the same season."""
    conn.execute(
        "DELETE FROM quotations WHERE source = ? AND scrape_date = ?",
        (source, scrape_date),
    )
    conn.commit()


def get_source_weights(conn: sqlite3.Connection) -> dict:
    cursor = conn.execute("SELECT name, weight FROM sources")
    return {row["name"]: row["weight"] for row in cursor.fetchall()}


def set_source_weight(conn: sqlite3.Connection, name: str, weight: float) -> None:
    conn.execute(
        """
        INSERT INTO sources (name, weight) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET weight = excluded.weight
        """,
        (name, weight),
    )
    conn.commit()


def get_price_history(conn: sqlite3.Connection, player_id: int) -> list:
    """Full time series of every quotation ever recorded for this player,
    one row per (source, scrape_date) — never overwritten, so this is the
    real historical record (spec section 4), not just the latest snapshot."""
    cursor = conn.execute(
        """
        SELECT source, scrape_date, price_current
        FROM quotations
        WHERE player_id = ? AND price_current IS NOT NULL
        ORDER BY scrape_date ASC, id ASC
        """,
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def upsert_player_source_match(conn: sqlite3.Connection, player_id: int, source: str,
                                source_name: str, source_team: str, confidence: float,
                                matched_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_source_matches
            (player_id, source, source_name, source_team, confidence, matched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, source) DO UPDATE SET
            source_name = excluded.source_name,
            source_team = excluded.source_team,
            confidence = excluded.confidence,
            matched_at = excluded.matched_at
        """,
        (player_id, source, source_name, source_team, confidence, matched_at),
    )
    conn.commit()


def get_low_confidence_matches(conn: sqlite3.Connection, threshold: float = 95.0) -> list:
    cursor = conn.execute(
        """
        SELECT m.player_id, m.source, m.source_name, m.source_team, m.confidence,
               m.matched_at, p.canonical_name, p.team
        FROM player_source_matches m
        JOIN players p ON p.id = m.player_id
        WHERE m.confidence < ?
        ORDER BY m.confidence ASC
        """,
        (threshold,),
    )
    return [dict(row) for row in cursor.fetchall()]


def replace_player_set_pieces(conn: sqlite3.Connection, source: str, entries: list) -> None:
    """entries: list of (player_id, category, rank, updated_at). A full
    re-crawl of the source page replaces everything from that source, since
    the page is a snapshot of the current hierarchy, not an incremental feed."""
    conn.execute("DELETE FROM player_set_pieces WHERE source = ?", (source,))
    for player_id, category, rank, updated_at in entries:
        conn.execute(
            """
            INSERT INTO player_set_pieces (player_id, category, rank, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (player_id, category, rank, source, updated_at),
        )
    conn.commit()


def get_player_set_pieces(conn: sqlite3.Connection, player_id: int) -> list:
    cursor = conn.execute(
        """
        SELECT category, rank, source, updated_at
        FROM player_set_pieces
        WHERE player_id = ?
        ORDER BY category, rank
        """,
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def upsert_match_rating(conn: sqlite3.Connection, player_id: int, season: str,
                         giornata: int, voto, fantavoto, source: str, updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_match_ratings
            (player_id, season, giornata, voto, fantavoto, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, season, giornata, source) DO UPDATE SET
            voto = excluded.voto,
            fantavoto = excluded.fantavoto,
            updated_at = excluded.updated_at
        """,
        (player_id, season, giornata, voto, fantavoto, source, updated_at),
    )
    conn.commit()


def get_recent_match_ratings(conn: sqlite3.Connection, player_id: int, limit: int = 5) -> list:
    cursor = conn.execute(
        """
        SELECT season, giornata, voto, fantavoto, source, updated_at
        FROM player_match_ratings
        WHERE player_id = ?
        ORDER BY season DESC, giornata DESC
        LIMIT ?
        """,
        (player_id, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_player_injuries(conn: sqlite3.Connection, player_id: int) -> list:
    cursor = conn.execute(
        """
        SELECT season, injury_type, date_from, date_to, days_out, matches_missed
        FROM player_injuries
        WHERE player_id = ?
        ORDER BY id DESC
        """,
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]
