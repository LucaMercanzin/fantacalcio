import json
import sqlite3

from matching.player_matcher import normalize_name, normalize_team


def upsert_player(conn: sqlite3.Connection, canonical_name: str, team: str,
                   role_classic: str, role_mantra, photo_path) -> int:
    # Looked up by identity_key, not by the display strings (TASK-007/
    # P0-007): canonical_name/team are whichever source happened to report
    # the longest name/team that day (matching.player_matcher.match_records)
    # and can change run to run if that source goes missing. Keying the
    # lookup on them turned a dropped scraper into a brand-new player row
    # that orphaned all of the old one's history (notes, roster, quotations).
    # canonical_name/team are kept as first-seen once a row exists — not
    # overwritten here — so the display name doesn't flip-flop with whichever
    # source responded that run; TASK-007 point 4 (choosing them
    # deterministically by source weight) is separate follow-up work.
    #
    # NOTE (residual limitation, see OPUS_PROJECT_REVIEW.md TASK-007 report):
    # this only protects the case where the *same* normalized name/team keeps
    # recurring. It does not by itself resolve P0-007's headline example (a
    # long-name source going down entirely, so a *shorter* name wins
    # `max(key=len)` and normalizes differently) — a prototype that
    # fuzzy-matched against existing players there was tried and reverted:
    # verified on the real test suite to silently merge distinct
    # similarly-named players (e.g. two "Filler A"/"Filler B" test fixtures)
    # when only one candidate existed yet to trigger the ambiguity guard.
    # Closing that gap safely needs its own task, not a quick addition here.
    identity_key = f"{normalize_name(canonical_name)}|{normalize_team(team)}"
    cursor = conn.execute(
        "SELECT id FROM players WHERE identity_key = ?", (identity_key,),
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
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra, "
        "photo_path, identity_key) VALUES (?, ?, ?, ?, ?, ?)",
        (canonical_name, team, role_classic, role_mantra, photo_path, identity_key),
    )
    conn.commit()
    return cursor.lastrowid


def count_players(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]


def insert_quotation(conn: sqlite3.Connection, player_id: int, source: str,
                      scrape_date: str, price_current, price_initial, status,
                      fantamedia, avg_rating, appearances) -> None:
    # ON CONFLICT keyed on the same (player_id, source, scrape_date) the
    # schema's idx_quotations_unique enforces (TASK-006/P1-016): re-scraping
    # the same source on the same day updates that row in place instead of
    # adding a duplicate.
    conn.execute(
        "INSERT INTO quotations (player_id, source, scrape_date, price_current, "
        "price_initial, status, fantamedia, avg_rating, appearances) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(player_id, source, scrape_date) DO UPDATE SET "
        "price_current = excluded.price_current, "
        "price_initial = excluded.price_initial, "
        "status = excluded.status, "
        "fantamedia = excluded.fantamedia, "
        "avg_rating = excluded.avg_rating, "
        "appearances = excluded.appearances",
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

# A match a human marked 🔴 "non è la stessa persona" (see
# set_match_review_status) must stop contributing to that player's
# consensus — the fuzzy matcher put it there, a person overruled it.
_EXCLUDE_REJECTED_MATCHES = """ AND NOT EXISTS (
    SELECT 1 FROM player_source_matches m
    WHERE m.player_id = q.player_id AND m.source = q.source
      AND m.review_status = 'rejected'
)"""


def get_latest_quotations(conn: sqlite3.Connection, role_classic: str) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.role_classic = ?
          """ + _EXCLUDE_HISTORICAL + _EXCLUDE_REJECTED_MATCHES + """
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
        WHERE 1=1""" + _EXCLUDE_HISTORICAL + _EXCLUDE_REJECTED_MATCHES + """
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


def get_source_price_p99(conn: sqlite3.Connection) -> dict:
    """99th percentile of each source's latest price_current — the
    per-source calibration point dashboard.data_access.compute_source_scale_
    factors uses to rescale every source onto a common canonical scale
    before averaging (P0-001/TASK-001): sources publish price_current on 5
    different, mutually incompatible raw scales (confirmed on the real DB:
    p99 ranges from 28 for fantacalcio_it to 248 for fantanalisi)."""
    rows = get_all_latest_quotations(conn)
    by_source = {}
    for row in rows:
        if row["price_current"] is not None:
            by_source.setdefault(row["source"], []).append(row["price_current"])
    result = {}
    for source, values in by_source.items():
        values.sort()
        idx = round(0.99 * (len(values) - 1))
        result[source] = values[idx]
    return result


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


# One row per data table tracked in Monitoraggio (TASK-004 point 4): which
# pipeline populates it and which column marks "when was this last written".
# date_column=None means the table has no reliable freshness column (e.g.
# player_injuries only has date_from/date_to, which describe the injury, not
# the scrape) — health for those tables is row-count-only.
TABLE_HEALTH_SPECS = [
    ("quotations", "Quotazioni/prezzi", "scrape_date", "pipeline/run_scraping.py"),
    ("player_season_stats", "Storico stagioni", "scraped_at", "pipeline/run_fcp_metrics.py"),
    ("player_match_ratings", "Fantavoti per giornata", "updated_at", "pipeline/run_match_ratings.py"),
    ("player_set_pieces", "Calci piazzati", "updated_at", "pipeline/run_set_pieces.py"),
    ("player_injuries", "Storico infortuni", None, "pipeline/run_injuries.py"),
    ("player_anagrafica", "Anagrafica", "updated_at", "pipeline/run_player_anagrafica.py"),
    ("player_advanced_stats", "Percentili avanzati (xG/xA)", "scrape_date", "pipeline/run_player_advanced_stats.py"),
    ("player_fantanalisi_valuations", "Valutazioni Fantanalisi", "scrape_date", "pipeline/run_fantanalisi_valuations.py"),
    ("team_strength", "Forza squadra (Understat)", "scrape_date", "pipeline/run_team_strength.py"),
    ("team_fixture_difficulty", "Difficoltà calendario", "scrape_date", "pipeline/run_fixture_difficulty.py"),
]


def get_table_health(conn: sqlite3.Connection) -> list:
    """Row count + last-write date for every table in TABLE_HEALTH_SPECS, so
    Monitoraggio can show which pipelines have genuinely never run instead of
    letting an empty table read as "nothing wrong" (P0-008, TASK-004).

    A table can be entirely missing from a committed DB that predates a
    schema change (P2-014: 4 tables from schema.sql were absent from the
    committed data/fantacalcio.db) — that is the reddest possible state, not
    an error, so it is reported as row_count=0 rather than raised."""
    health = []
    for table, label, date_column, pipeline in TABLE_HEALTH_SPECS:
        try:
            if date_column:
                cursor = conn.execute(
                    f"SELECT COUNT(*) AS row_count, MAX({date_column}) AS last_update FROM {table}"
                )
            else:
                cursor = conn.execute(f"SELECT COUNT(*) AS row_count, NULL AS last_update FROM {table}")
            row = cursor.fetchone()
            row_count, last_update = row["row_count"], row["last_update"]
        except sqlite3.OperationalError:
            row_count, last_update = 0, None
        health.append({
            "table": table,
            "label": label,
            "pipeline": pipeline,
            "row_count": row_count,
            "last_update": last_update,
        })
    return health


def get_latest_quotations_for_player(conn: sqlite3.Connection, player_id: int) -> list:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.id = ?
          """ + _EXCLUDE_HISTORICAL + _EXCLUDE_REJECTED_MATCHES + """
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
    # Upsert (idx_my_roster_player), not a plain INSERT: a double-submitted
    # form or a correction after a typo updates the existing entry instead
    # of erroring or silently double-counting the player in budget/slot math
    # (P1-017/TASK-020). A player can't be simultaneously mine and an
    # opponent's, so claiming him here also clears any opponent_picks row.
    conn.execute(
        "INSERT INTO my_roster (player_id, price_paid, date_added) VALUES (?, ?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET price_paid = excluded.price_paid, "
        "date_added = excluded.date_added",
        (player_id, price_paid, date_added),
    )
    conn.execute("DELETE FROM opponent_picks WHERE player_id = ?", (player_id,))
    conn.commit()


def remove_roster_entry(conn: sqlite3.Connection, player_id: int) -> None:
    conn.execute("DELETE FROM my_roster WHERE player_id = ?", (player_id,))
    conn.commit()


def get_roster(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        """
        SELECT r.id, r.player_id, r.price_paid, r.date_added,
               p.canonical_name, p.team, p.role_classic
        FROM my_roster r
        JOIN players p ON p.id = r.player_id
        ORDER BY r.date_added, r.id
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def add_opponent_pick(conn: sqlite3.Connection, player_id: int, opponent_name: str,
                       price_paid, date_added: str) -> None:
    # Upsert (opponent_picks.UNIQUE(player_id)): re-marking a player (a
    # correction — wrong opponent name, wrong price) updates the existing
    # row instead of raising IntegrityError (P1-017/TASK-020: "a typo during
    # a live auction is irreversible" — this was the other half of that,
    # my_roster's add_roster_entry above is the other). A player can't be
    # simultaneously an opponent's and mine, so this also clears him from
    # my_roster if he was there.
    conn.execute(
        "INSERT INTO opponent_picks (player_id, opponent_name, price_paid, date_added) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET opponent_name = excluded.opponent_name, "
        "price_paid = excluded.price_paid, date_added = excluded.date_added",
        (player_id, opponent_name, price_paid, date_added),
    )
    conn.execute("DELETE FROM my_roster WHERE player_id = ?", (player_id,))
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
        ORDER BY o.date_added, o.id
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


def get_all_player_notes(conn: sqlite3.Connection) -> dict:
    """{player_id: notes} for every annotated player in one query — the role
    pages enrich one row per player (150+ rows), and calling get_player_notes
    per row was the single N+1 left on the dashboard path (audit)."""
    cursor = conn.execute("SELECT player_id, notes FROM player_notes")
    return {row["player_id"]: row["notes"] for row in cursor.fetchall()}


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


def get_source_stats_weights(conn: sqlite3.Connection) -> dict:
    """Weight used for everything that isn't the price/credit consensus
    (fantamedia, media voto, presenze) — separate from get_source_weights so
    a source trusted for real auction credits doesn't automatically drown
    out the dedicated stats sources too."""
    cursor = conn.execute("SELECT name, weight_stats FROM sources")
    return {row["name"]: row["weight_stats"] for row in cursor.fetchall()}


def set_source_stats_weight(conn: sqlite3.Connection, name: str, weight: float) -> None:
    conn.execute(
        """
        INSERT INTO sources (name, weight, weight_stats) VALUES (?, 1, ?)
        ON CONFLICT(name) DO UPDATE SET weight_stats = excluded.weight_stats
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
               m.matched_at, m.review_status, p.canonical_name, p.team
        FROM player_source_matches m
        JOIN players p ON p.id = m.player_id
        WHERE m.confidence < ?
        ORDER BY m.confidence ASC
        """,
        (threshold,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_match_confidences(conn: sqlite3.Connection) -> dict:
    """player_id -> lowest per-source match confidence (0-100): the weakest
    link in "is every source's quotation actually about this player" is
    what should pull data_confidence down, not an average that a single
    badly-matched source could get diluted away in (TASK-010 point 2)."""
    cursor = conn.execute(
        "SELECT player_id, MIN(confidence) AS min_confidence "
        "FROM player_source_matches GROUP BY player_id"
    )
    return {row["player_id"]: row["min_confidence"] for row in cursor.fetchall()}


def set_match_review_status(conn: sqlite3.Connection, player_id: int, source: str,
                             status: str) -> None:
    """status: 'confirmed' (🟢 stessa persona), 'unsure' (🟡), 'rejected' (🔴
    persone diverse — la quotazione di questa fonte smette di contare per
    questo giocatore, vedi _EXCLUDE_REJECTED_MATCHES)."""
    conn.execute(
        "UPDATE player_source_matches SET review_status = ? "
        "WHERE player_id = ? AND source = ?",
        (status, player_id, source),
    )
    conn.commit()


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


def save_fcp_metrics(conn: sqlite3.Connection, player_id: int, scrape_date: str,
                      alg_fcp, punteggio_fcp, investment_stability_pct,
                      injury_resistance_pct, predicted_appearances,
                      predicted_goals, predicted_assists, skills: list) -> None:
    conn.execute(
        """
        INSERT INTO fcp_metrics
            (player_id, scrape_date, alg_fcp, punteggio_fcp,
             investment_stability_pct, injury_resistance_pct,
             predicted_appearances, predicted_goals, predicted_assists, skills)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (player_id, scrape_date, alg_fcp, punteggio_fcp, investment_stability_pct,
         injury_resistance_pct, predicted_appearances, predicted_goals,
         predicted_assists, json.dumps(skills or [])),
    )
    conn.commit()


def get_latest_fcp_metrics(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT * FROM fcp_metrics
        WHERE player_id = ?
        ORDER BY scrape_date DESC, id DESC
        LIMIT 1
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    result = dict(row)
    result["skills"] = json.loads(result["skills"]) if result["skills"] else []
    return result


def get_data_version(conn: sqlite3.Connection) -> tuple:
    """Cheap fingerprint of everything that can change the ranked-role
    computation (dashboard.data_access._compute_ranked_role): new quotations
    or FCP scrapes, a source weight adjusted by the admin, or a fuzzy match
    rejected in Monitoraggio. All are single indexed-PK lookups on small
    tables, so this is effectively instant — meant to be called on every
    request as the cache key for the expensive multi-source merge, so that
    merge is recomputed exactly when the underlying data actually changes
    instead of on a blind timer.
    """
    cursor = conn.execute(
        """
        SELECT
            (SELECT MAX(id) FROM quotations),
            (SELECT MAX(id) FROM fcp_metrics),
            (SELECT SUM(weight * 1000 + weight_stats) FROM sources),
            (SELECT COUNT(*) FROM player_source_matches WHERE review_status = 'rejected')
        """
    )
    return tuple(cursor.fetchone())


def get_auction_data_version(conn: sqlite3.Connection) -> tuple:
    """get_data_version extended with my_roster/opponent_picks (DA9/
    TASK-026): Auction Intelligence's budget_remaining/scarcity/max_bid all
    depend on the roster and on opponents' recorded picks, on top of the
    ranked-role consensus get_data_version already fingerprints. A cache
    keyed only on a blind ttl (30s) served a stale budget for up to half a
    minute after every purchase registered mid-auction."""
    base = get_data_version(conn)
    cursor = conn.execute(
        "SELECT (SELECT MAX(id) FROM my_roster), (SELECT MAX(id) FROM opponent_picks)"
    )
    return base + tuple(cursor.fetchone())


def get_all_latest_fcp_metrics(conn: sqlite3.Connection) -> dict:
    """player_id -> latest fcp_metrics row, for bulk merge into ranking rows."""
    cursor = conn.execute(
        """
        SELECT f.* FROM fcp_metrics f
        WHERE f.id = (
            SELECT f2.id FROM fcp_metrics f2
            WHERE f2.player_id = f.player_id
            ORDER BY f2.scrape_date DESC, f2.id DESC
            LIMIT 1
        )
        """
    )
    result = {}
    for row in cursor.fetchall():
        entry = dict(row)
        entry["skills"] = json.loads(entry["skills"]) if entry["skills"] else []
        result[entry["player_id"]] = entry
    return result


def upsert_player_season_stats(conn: sqlite3.Connection, player_id: int, source: str,
                                seasons: list, scraped_at: str) -> None:
    """seasons: scrapers.fantacalciopedia.parse_season_stats output for this
    player. Upsert (not delete-then-insert like replace_player_injuries):
    a season's stats get refreshed in place on re-scrape rather than
    accumulating dated duplicates — UNIQUE(player_id, season, source) is the
    natural key, there's only ever one "current" row per season per source."""
    for season in seasons:
        conn.execute(
            """
            INSERT INTO player_season_stats
                (player_id, season, source, appearances, goals_scored, goals_conceded,
                 assists, avg_rating, yellow_cards, red_cards, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, season, source) DO UPDATE SET
                appearances = excluded.appearances,
                goals_scored = excluded.goals_scored,
                goals_conceded = excluded.goals_conceded,
                assists = excluded.assists,
                avg_rating = excluded.avg_rating,
                yellow_cards = excluded.yellow_cards,
                red_cards = excluded.red_cards,
                scraped_at = excluded.scraped_at
            """,
            (player_id, season["season"], source, season["appearances"],
             season.get("goals_scored"), season.get("goals_conceded"), season["assists"],
             season.get("avg_rating"), season["yellow_cards"], season["red_cards"], scraped_at),
        )
    conn.commit()


def insert_team_strength(conn: sqlite3.Connection, team: str, xg, xga, ppda,
                          source: str, scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO team_strength (team, xg, xga, ppda, source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(team, source, scrape_date) DO UPDATE SET
            xg = excluded.xg, xga = excluded.xga, ppda = excluded.ppda
        """,
        (team, xg, xga, ppda, source, scrape_date),
    )
    conn.commit()


def get_all_latest_team_strength(conn: sqlite3.Connection) -> dict:
    """team -> ultima riga scrappata (xg/xga/ppda/scrape_date), una per
    squadra — stesso pattern di get_all_latest_fcp_metrics."""
    cursor = conn.execute(
        """
        SELECT t.* FROM team_strength t
        WHERE t.id = (
            SELECT t2.id FROM team_strength t2
            WHERE t2.team = t.team
            ORDER BY t2.scrape_date DESC, t2.id DESC
            LIMIT 1
        )
        """
    )
    return {row["team"]: dict(row) for row in cursor.fetchall()}


def get_all_latest_player_season_stats(conn: sqlite3.Connection) -> dict:
    """player_id -> most recent season's row (by season string, descending),
    for bulk merge into ranking rows — same pattern as
    get_all_latest_fcp_metrics."""
    cursor = conn.execute(
        """
        SELECT s.* FROM player_season_stats s
        WHERE s.id = (
            SELECT s2.id FROM player_season_stats s2
            WHERE s2.player_id = s.player_id
            ORDER BY s2.season DESC, s2.id DESC
            LIMIT 1
        )
        """
    )
    return {row["player_id"]: dict(row) for row in cursor.fetchall()}


def get_all_player_set_pieces(conn: sqlite3.Connection) -> dict:
    """player_id -> list of {category, rank, source, updated_at}, for bulk
    merge into ranking rows — same pattern as get_all_latest_fcp_metrics."""
    cursor = conn.execute(
        "SELECT player_id, category, rank, source, updated_at FROM player_set_pieces"
    )
    result: dict = {}
    for row in cursor.fetchall():
        result.setdefault(row["player_id"], []).append({
            "category": row["category"], "rank": row["rank"],
            "source": row["source"], "updated_at": row["updated_at"],
        })
    return result


def get_player_season_stats(conn: sqlite3.Connection, player_id: int) -> list:
    """Most recent season first. A player can in principle have rows from
    more than one source (source is part of the key) — ordering by season
    only, since today there's just one (fantacalciopedia)."""
    cursor = conn.execute(
        """
        SELECT * FROM player_season_stats
        WHERE player_id = ?
        ORDER BY season DESC
        """,
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def upsert_player_anagrafica(conn: sqlite3.Connection, player_id: int, birth_date,
                              height_cm, foot, nationality, shirt_number,
                              updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_anagrafica
            (player_id, birth_date, height_cm, foot, nationality, shirt_number, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            birth_date = excluded.birth_date, height_cm = excluded.height_cm,
            foot = excluded.foot, nationality = excluded.nationality,
            shirt_number = excluded.shirt_number, updated_at = excluded.updated_at
        """,
        (player_id, birth_date, height_cm, foot, nationality, shirt_number, updated_at),
    )
    conn.commit()


def get_player_anagrafica(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT birth_date, height_cm, foot, nationality, shirt_number
        FROM player_anagrafica WHERE player_id = ?
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def insert_player_advanced_stats(conn: sqlite3.Connection, player_id: int,
                                  xg90_percentile, xa90_percentile, shots90_percentile,
                                  key_passes90_percentile, involvement_percentile,
                                  minutes_percentile, source: str, scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO player_advanced_stats
            (player_id, xg90_percentile, xa90_percentile, shots90_percentile,
             key_passes90_percentile, involvement_percentile, minutes_percentile,
             source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, source, scrape_date) DO UPDATE SET
            xg90_percentile = excluded.xg90_percentile,
            xa90_percentile = excluded.xa90_percentile,
            shots90_percentile = excluded.shots90_percentile,
            key_passes90_percentile = excluded.key_passes90_percentile,
            involvement_percentile = excluded.involvement_percentile,
            minutes_percentile = excluded.minutes_percentile
        """,
        (player_id, xg90_percentile, xa90_percentile, shots90_percentile,
         key_passes90_percentile, involvement_percentile, minutes_percentile,
         source, scrape_date),
    )
    conn.commit()


def get_latest_player_advanced_stats(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT xg90_percentile, xa90_percentile, shots90_percentile,
               key_passes90_percentile, involvement_percentile, minutes_percentile,
               scrape_date
        FROM player_advanced_stats
        WHERE player_id = ?
        ORDER BY scrape_date DESC, id DESC
        LIMIT 1
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def insert_team_fixture_difficulty(conn: sqlite3.Connection, team: str,
                                    difficulty_attack, difficulty_defense,
                                    window_label: str, source: str,
                                    scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO team_fixture_difficulty
            (team, difficulty_attack, difficulty_defense, window_label, source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(team, window_label, source, scrape_date) DO UPDATE SET
            difficulty_attack = excluded.difficulty_attack,
            difficulty_defense = excluded.difficulty_defense
        """,
        (team, difficulty_attack, difficulty_defense, window_label, source, scrape_date),
    )
    conn.commit()


def get_all_latest_team_fixture_difficulty(conn: sqlite3.Connection,
                                            window_label: str = "prime 5 giornate") -> dict:
    cursor = conn.execute(
        """
        SELECT team, difficulty_attack, difficulty_defense, scrape_date
        FROM team_fixture_difficulty t1
        WHERE window_label = ? AND scrape_date = (
            SELECT MAX(scrape_date) FROM team_fixture_difficulty t2
            WHERE t2.team = t1.team AND t2.window_label = t1.window_label
        )
        """,
        (window_label,),
    )
    return {row["team"]: dict(row) for row in cursor.fetchall()}


def insert_player_fantanalisi_valuation(conn: sqlite3.Connection, player_id: int,
                                         fair_price_range, max_bid, tier, risk,
                                         source: str, scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO player_fantanalisi_valuations
            (player_id, fair_price_range, max_bid, tier, risk, source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, source, scrape_date) DO UPDATE SET
            fair_price_range = excluded.fair_price_range,
            max_bid = excluded.max_bid, tier = excluded.tier, risk = excluded.risk
        """,
        (player_id, fair_price_range, max_bid, tier, risk, source, scrape_date),
    )
    conn.commit()


def get_latest_player_fantanalisi_valuation(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT fair_price_range, max_bid, tier, risk, scrape_date
        FROM player_fantanalisi_valuations
        WHERE player_id = ?
        ORDER BY scrape_date DESC, id DESC
        LIMIT 1
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None
