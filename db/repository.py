import json
import sqlite3
from datetime import datetime

from config import CURRENT_SEASON
from matching.player_matcher import normalize_name, normalize_team


def start_scraping_run(conn: sqlite3.Connection, weights_json: str | None = None) -> int:
    """One row per pipeline/run_scraping.run_pipeline call (TASK-006):
    committed immediately (unlike the per-record writes the run makes
    later, batched with commit=False) so the run is visible as 'running'
    even if the process is killed outright before it can call
    finish_scraping_run.

    weights_json (TASK-013 point 4): a JSON snapshot of the price/stats
    weights this run used, recorded at start since they're fixed at that
    point — an admin can change them in Monitoraggio at any time
    afterwards, so this is what makes an old player_consensus row
    reproducible/explainable later."""
    cursor = conn.execute(
        "INSERT INTO scraping_runs (started_at, status, weights_json) VALUES (?, 'running', ?)",
        (datetime.now().isoformat(timespec="seconds"), weights_json),
    )
    conn.commit()
    return cursor.lastrowid


def finish_scraping_run(conn: sqlite3.Connection, run_id: int, status: str,
                         sources_ok: int, sources_failed: int, records_written: int,
                         players_added: int | None = None, players_removed: int | None = None,
                         players_transferred: int | None = None, players_unchanged: int | None = None) -> None:
    # players_* default to None (TASK-004c point 4): a failed run never
    # reaches the ADDED/REMOVED/TRANSFERRED/UNCHANGED accounting, and
    # players_removed specifically stays None even on an ok run whose
    # sources weren't all ok (absence marking only happens on a complete
    # run — see run_pipeline) rather than being reported as a false 0.
    conn.execute(
        "UPDATE scraping_runs SET finished_at = ?, status = ?, sources_ok = ?, "
        "sources_failed = ?, records_written = ?, players_added = ?, "
        "players_removed = ?, players_transferred = ?, players_unchanged = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), status, sources_ok,
         sources_failed, records_written, players_added, players_removed,
         players_transferred, players_unchanged, run_id),
    )
    conn.commit()


def save_player_consensus(conn: sqlite3.Connection, row: dict, scrape_date: str,
                           commit: bool = True) -> None:
    """Persists one player's merged consensus row (consensus.engine.
    _merge_player_rows output) for `scrape_date` (TASK-013). ON CONFLICT
    keyed on (player_id, scrape_date): a re-scrape on the same day replaces
    that day's snapshot instead of accumulating duplicates."""
    conn.execute(
        """
        INSERT INTO player_consensus
            (player_id, scrape_date, price_listino, price_auction, price_basis,
             fantamedia, avg_rating, appearances, source_count, price_agreement,
             data_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, scrape_date) DO UPDATE SET
            price_listino = excluded.price_listino,
            price_auction = excluded.price_auction,
            price_basis = excluded.price_basis,
            fantamedia = excluded.fantamedia,
            avg_rating = excluded.avg_rating,
            appearances = excluded.appearances,
            source_count = excluded.source_count,
            price_agreement = excluded.price_agreement,
            data_confidence = excluded.data_confidence
        """,
        (row["player_id"], scrape_date, row.get("price_listino"), row.get("price_auction"),
         row.get("price_basis"), row.get("fantamedia"), row.get("avg_rating"),
         row.get("appearances"), row.get("source_count"), row.get("price_agreement"),
         row.get("data_confidence")),
    )
    if commit:
        conn.commit()


def get_player_consensus_history(conn: sqlite3.Connection, player_id: int) -> list:
    """Ogni istantanea storica del consenso per un giocatore, più recente
    prima — risponde a "qual era il prezzo di consenso di X il giorno Y"
    (TASK-013, acceptance criteria)."""
    cursor = conn.execute(
        "SELECT * FROM player_consensus WHERE player_id = ? ORDER BY scrape_date DESC",
        (player_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_player_consensus_on_date(conn: sqlite3.Connection, player_id: int, scrape_date: str):
    row = conn.execute(
        "SELECT * FROM player_consensus WHERE player_id = ? AND scrape_date = ?",
        (player_id, scrape_date),
    ).fetchone()
    return dict(row) if row else None


def get_current_season_team_codes(conn: sqlite3.Connection) -> set:
    """normalize_team()-keyed set of the current season's real clubs, from
    the `teams` table — the one place TASK-005's per-record validation
    checks a scraped team against, instead of accepting anything a scraper
    happens to report (a typo'd/foreign/lower-league team used to sail
    straight into quotations with no check at all)."""
    cursor = conn.execute("SELECT code FROM teams WHERE season = ?", (CURRENT_SEASON,))
    return {row["code"] for row in cursor.fetchall()}


def get_team_aliases(conn: sqlite3.Connection) -> dict:
    """matching.player_matcher.normalize_team's alias_map (TASK-009/D9):
    letters-only-lowercase full/official name -> team code, for club-name
    variants ("AS Roma", "Hellas Verona") a plain 3-letter truncation gets
    wrong. Admin-editable via this table, same convention as the `sources`
    weights."""
    cursor = conn.execute("SELECT alias, team_code FROM team_aliases")
    return {row["alias"]: row["team_code"] for row in cursor.fetchall()}


def get_player_id_by_identity(conn: sqlite3.Connection, canonical_name: str, team: str,
                               alias_map: dict | None = None):
    """Read-only lookup by the same identity_key upsert_player uses, for
    callers that need to know a player's id *before* deciding whether to
    write anything (TASK-027/S6: pipeline/run_scraping.py checks for an
    already-downloaded photo file, which needs the id to name, without
    forcing a write just to find out).

    alias_map (TASK-009/D9): must match whatever upsert_player was called
    with for this player, or a club-name variant ("AS Roma") normalizes to
    a different identity_key here than the one already stored and this
    lookup misses a player who actually exists."""
    identity_key = f"{normalize_name(canonical_name)}|{normalize_team(team, alias_map)}"
    row = conn.execute(
        "SELECT id FROM players WHERE identity_key = ?", (identity_key,),
    ).fetchone()
    return row["id"] if row else None


def get_players_by_normalized_name(conn: sqlite3.Connection, canonical_name: str) -> list:
    """Every player sharing normalize_name(canonical_name), regardless of
    team (TASK-004c/P0-010) — candidates for telling a real team change
    apart from a brand-new player. NOT the primary identity lookup (that
    stays get_player_id_by_identity, keyed on name+team): only consulted by
    run_pipeline when that exact lookup misses, and only acted on when it
    returns a single candidate — with 2+ same-named players there's no safe
    way to tell which one (if any) actually transferred, so the caller falls
    back to treating the record as a new player rather than risk merging two
    different people (see the fuzzy-match prototype reverted under TASK-007
    for exactly this failure mode)."""
    target = normalize_name(canonical_name)
    rows = conn.execute("SELECT id, canonical_name, team FROM players").fetchall()
    return [dict(r) for r in rows if normalize_name(r["canonical_name"]) == target]


def update_player_team(conn: sqlite3.Connection, player_id: int, new_team: str, commit: bool = True,
                        alias_map: dict | None = None) -> None:
    """Moves an existing player to a new team in place (TASK-004c/P0-010),
    recomputing identity_key so the upsert_player call that follows (same
    canonical_name/new team) finds this row instead of creating a second
    one — the bug this task fixes."""
    row = conn.execute("SELECT canonical_name FROM players WHERE id = ?", (player_id,)).fetchone()
    identity_key = f"{normalize_name(row['canonical_name'])}|{normalize_team(new_team, alias_map)}"
    conn.execute(
        "UPDATE players SET team = ?, identity_key = ? WHERE id = ?",
        (new_team, identity_key, player_id),
    )
    if commit:
        conn.commit()


def record_player_transfer(conn: sqlite3.Connection, player_id: int, from_team: str, to_team: str,
                            detected_at: str, commit: bool = True) -> None:
    conn.execute(
        "INSERT INTO player_transfers (player_id, from_team, to_team, detected_at) VALUES (?, ?, ?, ?)",
        (player_id, from_team, to_team, detected_at),
    )
    if commit:
        conn.commit()


def mark_players_seen(conn: sqlite3.Connection, player_ids, scrape_date: str, commit: bool = True) -> None:
    """Every player upserted during this run (TASK-004c point 3): reactivates
    a player who returns after being marked inactive, and records this as
    the last run he was actually seen in."""
    conn.executemany(
        "UPDATE players SET active = 1, last_seen_scrape_date = ? WHERE id = ?",
        [(scrape_date, player_id) for player_id in player_ids],
    )
    if commit:
        conn.commit()


def mark_players_not_seen_inactive(conn: sqlite3.Connection, scrape_date: str, commit: bool = True) -> int:
    """Marks inactive every currently-active player NOT seen in this run
    (TASK-004c point 3) — never deleted, so his history stays intact. Only
    call this after a *complete* run (every source ok): run_pipeline skips
    it otherwise, since a single dropped scraper would otherwise mark every
    player that source alone covers as gone."""
    cursor = conn.execute(
        "UPDATE players SET active = 0 WHERE active = 1 AND "
        "(last_seen_scrape_date IS NULL OR last_seen_scrape_date != ?)",
        (scrape_date,),
    )
    if commit:
        conn.commit()
    return cursor.rowcount


def upsert_player(conn: sqlite3.Connection, canonical_name: str, team: str,
                   role_classic: str, role_mantra, photo_path, commit: bool = True,
                   alias_map: dict | None = None) -> int:
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
    #
    # A genuine team change (name unchanged) IS handled, separately (TASK-
    # 004c/P0-010): run_pipeline calls get_players_by_normalized_name +
    # update_player_team *before* reaching here whenever this exact
    # identity_key misses and exactly one existing player shares the
    # incoming record's normalized name — by the time upsert_player runs,
    # that player's row (and identity_key) already reflects the new team, so
    # the SELECT below finds it instead of falling through to INSERT.
    identity_key = f"{normalize_name(canonical_name)}|{normalize_team(team, alias_map)}"
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
        if commit:
            conn.commit()
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra, "
        "photo_path, identity_key) VALUES (?, ?, ?, ?, ?, ?)",
        (canonical_name, team, role_classic, role_mantra, photo_path, identity_key),
    )
    if commit:
        conn.commit()
    return cursor.lastrowid


def count_players(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]


def insert_quotation(conn: sqlite3.Connection, player_id: int, source: str,
                      scrape_date: str, price_current, price_initial, status,
                      fantamedia, avg_rating, appearances, commit: bool = True) -> None:
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
    if commit:
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
                                matched_at: str, commit: bool = True) -> None:
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
    if commit:
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
