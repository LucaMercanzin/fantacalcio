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


def get_latest_quotations(conn: sqlite3.Connection, role_classic: str) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.role_classic = ?
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
        WHERE q.id = (
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
