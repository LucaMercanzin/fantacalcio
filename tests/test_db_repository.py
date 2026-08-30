from db import repository
from db.connection import get_connection, init_db


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert {"players", "quotations", "my_roster", "player_notes"} <= tables
    conn.close()


def test_get_team_aliases_returns_seeded_club_name_variants(tmp_path):
    """TASK-009/D9: the seeded aliases must actually resolve to the same
    code their club's short name already normalizes to on its own."""
    from matching.player_matcher import normalize_team

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    aliases = repository.get_team_aliases(conn)

    assert aliases["asroma"] == normalize_team("Roma")
    assert aliases["sslazio"] == normalize_team("Lazio")
    conn.close()


def test_upsert_player_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    id1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    id2 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    assert id1 == id2
    conn.close()


def test_upsert_player_reuses_row_across_casing_and_abbreviation_variants(tmp_path):
    """TASK-007/P0-007: identity_key normalizes casing/punctuation, so a
    source spelling the same player/team slightly differently (e.g. an
    abbreviation vs. the full name in the exact same casing/punctuation
    shape) still resolves to the same row instead of orphaning history."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    id1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)
    id2 = repository.upsert_player(conn, "LAUTARO MARTINEZ", "INTER", "A", "Pu", None)

    assert id1 == id2
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1
    conn.close()


def test_migrate_backfills_identity_key_for_legacy_players(tmp_path):
    """TASK-007/P0-007: a DB written before identity_key existed (like the
    committed data/fantacalcio.db, verified 0 collisions across 803 players)
    needs _migrate() to add the column and backfill it, so upsert_player's
    identity_key lookup works against rows that predate the column."""
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL, team TEXT NOT NULL,
            role_classic TEXT NOT NULL, role_mantra TEXT, photo_path TEXT,
            UNIQUE(canonical_name, team)
        );
        """
    )
    conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic) "
        "VALUES ('Lautaro Martinez', 'Inter', 'A')"
    )
    conn.commit()
    conn.close()

    init_db(db_path)
    conn = get_connection(db_path)

    row = conn.execute("SELECT identity_key FROM players").fetchone()
    assert row["identity_key"] == "lautaro martinez|int"

    # The now-backfilled row is reachable through the normal upsert path.
    same_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1
    assert same_id == conn.execute("SELECT id FROM players").fetchone()[0]
    conn.close()


def test_insert_and_get_latest_quotations(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-01",
        price_current=35, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-10",
        price_current=38, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )

    latest = repository.get_latest_quotations(conn, role_classic="A")

    assert len(latest) == 1
    assert latest[0]["price_current"] == 38
    conn.close()


def test_migrate_dedupes_legacy_duplicate_quotations_and_adds_unique_index(tmp_path):
    """TASK-006/P1-016: insert_quotation's ON CONFLICT upsert only protects
    rows written after the UNIQUE(player_id, source, scrape_date) index
    exists. A DB created before that (like the committed data/fantacalcio.db,
    9327 rows for ~3509 distinct player/source/date triples) needs _migrate()
    to clean up the legacy duplicates and add the index retroactively."""
    db_path = str(tmp_path / "test.db")

    # Build a DB the way a pre-TASK-006 install would look: players +
    # quotations with no unique index at all (schema.sql's own CREATE TABLE
    # IF NOT EXISTS would be a no-op against this table on the next init_db,
    # same as it is against the real committed data/fantacalcio.db).
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL, team TEXT NOT NULL,
            role_classic TEXT NOT NULL, role_mantra TEXT, photo_path TEXT,
            UNIQUE(canonical_name, team)
        );
        CREATE TABLE quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            source TEXT NOT NULL, scrape_date TEXT NOT NULL,
            price_current REAL, price_initial REAL, status TEXT,
            fantamedia REAL, avg_rating REAL, appearances INTEGER
        );
        """
    )
    # Plain INSERT, not repository.upsert_player: that function now expects
    # an identity_key column (TASK-007) this legacy schema doesn't have yet
    # — exactly the pre-migration state _migrate() needs to backfill.
    cursor = conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra) "
        "VALUES ('Lautaro Martinez', 'Inter', 'A', 'Pu')"
    )
    player_id = cursor.lastrowid
    for price in (35, 36, 38):
        conn.execute(
            "INSERT INTO quotations (player_id, source, scrape_date, price_current) "
            "VALUES (?, 'fantacalcio_it', '2026-08-10', ?)",
            (player_id, price),
        )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM quotations").fetchone()[0] == 3
    conn.close()

    init_db(db_path)  # re-running init_db re-runs _migrate()
    conn = get_connection(db_path)

    rows = conn.execute(
        "SELECT price_current FROM quotations WHERE player_id = ?", (player_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["price_current"] == 38  # highest id (last inserted) survives

    unique_indexes = {
        row[1] for row in conn.execute("PRAGMA index_list(quotations)").fetchall()
        if row[2]  # unique flag
    }
    assert "idx_quotations_unique" in unique_indexes

    # Re-inserting the same (player, source, date) now upserts instead of
    # duplicating, confirming the index is actually enforced going forward.
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-10",
        price_current=40, price_initial=None, status=None,
        fantamedia=None, avg_rating=None, appearances=None,
    )
    assert conn.execute("SELECT COUNT(*) FROM quotations").fetchone()[0] == 1
    conn.close()


def test_migrate_dedupes_legacy_duplicate_roster_entries_and_adds_unique_index(tmp_path):
    """P1-017/TASK-020: same idempotency gap as quotations, for my_roster —
    a DB written before add_roster_entry's upsert could have real duplicate
    rows for the same player_id."""
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL, team TEXT NOT NULL,
            role_classic TEXT NOT NULL, role_mantra TEXT, photo_path TEXT,
            UNIQUE(canonical_name, team)
        );
        CREATE TABLE my_roster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            price_paid REAL NOT NULL, date_added TEXT NOT NULL
        );
        """
    )
    cursor = conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra) "
        "VALUES ('Lautaro Martinez', 'Inter', 'A', 'Pu')"
    )
    player_id = cursor.lastrowid
    for price in (38, 40):
        conn.execute(
            "INSERT INTO my_roster (player_id, price_paid, date_added) VALUES (?, ?, '2026-08-20')",
            (player_id, price),
        )
    conn.commit()
    conn.close()

    init_db(db_path)
    conn = get_connection(db_path)

    roster = repository.get_roster(conn)
    assert len(roster) == 1
    assert roster[0]["price_paid"] == 40  # highest id (last inserted) survives

    unique_indexes = {
        row[1] for row in conn.execute("PRAGMA index_list(my_roster)").fetchall()
        if row[2]
    }
    assert "idx_my_roster_player" in unique_indexes
    conn.close()


def test_roster_add_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")
    roster = repository.get_roster(conn)

    assert len(roster) == 1
    assert roster[0]["price_paid"] == 40
    conn.close()


def test_add_roster_entry_upserts_instead_of_duplicating(tmp_path):
    """P1-017/TASK-020: a double-submitted form (or a price correction)
    must update the existing entry, not create a second row that would
    double-count this player in budget/slot math."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")
    repository.add_roster_entry(conn, player_id, price_paid=45, date_added="2026-08-21")
    roster = repository.get_roster(conn)

    assert len(roster) == 1
    assert roster[0]["price_paid"] == 45
    conn.close()


def test_remove_roster_entry_deletes_it(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")

    repository.remove_roster_entry(conn, player_id)

    assert repository.get_roster(conn) == []
    conn.close()


def test_get_auction_data_version_changes_when_roster_or_opponent_picks_change(tmp_path):
    """DA9/TASK-026: budget_remaining (and everything Auction Intelligence
    derives from it) depends on my_roster/opponent_picks, not just on the
    ranked-role consensus get_data_version already fingerprints — a cache
    keyed only on those would serve a stale budget after a purchase."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    before = repository.get_auction_data_version(conn)
    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")
    after_roster = repository.get_auction_data_version(conn)
    assert after_roster != before

    opponent_player_id = repository.upsert_player(conn, "Osimhen Victor", "Napoli", "A", "Pu", None)
    repository.add_opponent_pick(conn, opponent_player_id, "Avversario1", 50, "2026-08-20")
    after_opponent = repository.get_auction_data_version(conn)
    assert after_opponent != after_roster
    conn.close()


def test_add_opponent_pick_upserts_instead_of_raising(tmp_path):
    """P1-017/TASK-020: re-marking a player (correcting a typo in the
    opponent name or price) must update the row, not raise IntegrityError —
    "an auction typo is irreversible" was the original finding."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_opponent_pick(conn, player_id, "Mario", 40, "2026-08-20")
    repository.add_opponent_pick(conn, player_id, "Luigi", 45, "2026-08-21")
    picks = repository.get_opponent_picks(conn)

    assert len(picks) == 1
    assert picks[0]["opponent_name"] == "Luigi"
    assert picks[0]["price_paid"] == 45
    conn.close()


def test_roster_and_opponent_picks_are_mutually_exclusive(tmp_path):
    """A player can't be simultaneously mine and an opponent's — claiming
    him one way must clear the other (TASK-020)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_opponent_pick(conn, player_id, "Mario", 40, "2026-08-20")
    repository.add_roster_entry(conn, player_id, price_paid=45, date_added="2026-08-21")

    assert len(repository.get_roster(conn)) == 1
    assert repository.get_opponent_picks(conn) == []

    repository.add_opponent_pick(conn, player_id, "Luigi", 50, "2026-08-22")

    assert repository.get_roster(conn) == []
    assert len(repository.get_opponent_picks(conn)) == 1
    conn.close()


def test_player_notes_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.upsert_player_notes(conn, player_id, "Ottimo investimento", "2026-08-20")
    repository.upsert_player_notes(conn, player_id, "Aggiornato: preferire vice", "2026-08-21")

    notes = repository.get_player_notes(conn, player_id)

    assert notes == "Aggiornato: preferire vice"
    conn.close()


def test_get_all_match_confidences_returns_lowest_per_player(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    p2 = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    repository.upsert_player_source_match(conn, p1, "fantacalcio_it", "Lautaro Martinez", "Inter", 100.0, "2026-08-24")
    repository.upsert_player_source_match(conn, p1, "gazzetta", "L. Martinez", "Inter", 82.0, "2026-08-24")
    repository.upsert_player_source_match(conn, p2, "fantacalcio_it", "Donyell Malen", "Roma", 100.0, "2026-08-24")

    confidences = repository.get_all_match_confidences(conn)

    assert confidences[p1] == 82.0
    assert confidences[p2] == 100.0
    conn.close()


def test_transfermarkt_id_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    repository.upsert_transfermarkt_id(conn, player_id, 326029, "2026-08-24")

    assert repository.get_transfermarkt_id(conn, player_id) == 326029
    conn.close()


def test_replace_player_injuries(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    injuries = [
        {"season": "24/25", "injury_type": "Malato", "date_from": "26/02/2025",
         "date_to": "03/03/2025", "days_out": 6, "matches_missed": 1},
        {"season": "23/24", "injury_type": "Problemi al ginocchio", "date_from": "14/04/2024",
         "date_to": "29/04/2024", "days_out": 16, "matches_missed": 3},
    ]
    repository.replace_player_injuries(conn, player_id, injuries)

    stored = repository.get_player_injuries(conn, player_id)
    assert len(stored) == 2
    assert stored[0]["injury_type"] in {"Malato", "Problemi al ginocchio"}

    repository.replace_player_injuries(conn, player_id, injuries[:1])
    stored = repository.get_player_injuries(conn, player_id)
    assert len(stored) == 1
    conn.close()


def test_save_and_get_latest_fcp_metrics(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Hojlund Rasmus", "Napoli", "A", "Pc", None)

    repository.save_fcp_metrics(
        conn, player_id, "2026-08-01",
        alg_fcp=90, punteggio_fcp=70, investment_stability_pct=50,
        injury_resistance_pct=50, predicted_appearances="25+",
        predicted_goals="8/10", predicted_assists="2/4",
        skills=["Titolare", "Goleador"],
    )
    repository.save_fcp_metrics(
        conn, player_id, "2026-08-20",
        alg_fcp=97, punteggio_fcp=75, investment_stability_pct=60,
        injury_resistance_pct=60, predicted_appearances="30+",
        predicted_goals="12/15", predicted_assists="3/5",
        skills=["Outsider", "Titolare", "Goleador", "Rigorista"],
    )

    latest = repository.get_latest_fcp_metrics(conn, player_id)
    assert latest["alg_fcp"] == 97
    assert latest["scrape_date"] == "2026-08-20"
    assert latest["skills"] == ["Outsider", "Titolare", "Goleador", "Rigorista"]
    conn.close()


def test_get_latest_fcp_metrics_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Nobody", "Roma", "A", "Pc", None)

    assert repository.get_latest_fcp_metrics(conn, player_id) is None
    conn.close()


def test_get_all_latest_fcp_metrics_returns_latest_per_player(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Player One", "Roma", "A", "Pc", None)
    p2 = repository.upsert_player(conn, "Player Two", "Roma", "A", "Pc", None)

    repository.save_fcp_metrics(
        conn, p1, "2026-08-01", alg_fcp=80, punteggio_fcp=60,
        investment_stability_pct=40, injury_resistance_pct=40,
        predicted_appearances=None, predicted_goals=None, predicted_assists=None,
        skills=[],
    )
    repository.save_fcp_metrics(
        conn, p2, "2026-08-01", alg_fcp=90, punteggio_fcp=70,
        investment_stability_pct=50, injury_resistance_pct=50,
        predicted_appearances=None, predicted_goals=None, predicted_assists=None,
        skills=[],
    )

    all_metrics = repository.get_all_latest_fcp_metrics(conn)

    assert set(all_metrics.keys()) == {p1, p2}
    assert all_metrics[p1]["alg_fcp"] == 80
    assert all_metrics[p2]["alg_fcp"] == 90
    conn.close()


def test_upsert_player_season_stats_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Test Player", "Roma", "A", "Pc", None)

    seasons = [
        {"season": "2025/26", "appearances": 35, "goals_scored": 10, "goals_conceded": None,
         "assists": 6, "avg_rating": 6.39, "yellow_cards": 2, "red_cards": 0},
        {"season": "2024/25", "appearances": 32, "goals_scored": 7, "goals_conceded": None,
         "assists": 3, "avg_rating": 6.33, "yellow_cards": 2, "red_cards": 1},
    ]
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", seasons, "2026-08-26")

    result = repository.get_player_season_stats(conn, player_id)

    assert len(result) == 2
    assert result[0]["season"] == "2025/26"  # most recent first
    assert result[0]["goals_scored"] == 10
    assert result[1]["season"] == "2024/25"
    conn.close()


def test_upsert_player_season_stats_refreshes_in_place_on_rescrape(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Test Player", "Roma", "A", "Pc", None)

    first = [{"season": "2025/26", "appearances": 10, "goals_scored": 2, "goals_conceded": None,
              "assists": 1, "avg_rating": 6.0, "yellow_cards": 0, "red_cards": 0}]
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", first, "2026-08-01")

    updated = [{"season": "2025/26", "appearances": 20, "goals_scored": 5, "goals_conceded": None,
                "assists": 2, "avg_rating": 6.5, "yellow_cards": 1, "red_cards": 0}]
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", updated, "2026-08-15")

    result = repository.get_player_season_stats(conn, player_id)

    assert len(result) == 1  # replaced, not duplicated
    assert result[0]["appearances"] == 20
    assert result[0]["goals_scored"] == 5
    conn.close()


def test_get_all_latest_player_season_stats_returns_most_recent_season(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "Nico Paz", "Como", "C", "T", None)

    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2024/25", "competition": "serie_a", "appearances": 30, "goals_scored": 5,
         "goals_conceded": None, "assists": 4, "avg_rating": 6.3, "yellow_cards": 3, "red_cards": 0},
        {"season": "2025/26", "competition": "serie_a", "appearances": 10, "goals_scored": 3,
         "goals_conceded": None, "assists": 2, "avg_rating": 6.6, "yellow_cards": 1, "red_cards": 0},
    ], scraped_at="2026-08-27")

    result = repository.get_all_latest_player_season_stats(conn)

    assert result[player_id]["season"] == "2025/26"
    assert result[player_id]["goals_scored"] == 3
    conn.close()


def test_get_all_latest_player_season_stats_excludes_non_serie_a_and_stale_seasons(tmp_path):
    """TASK-008/P0-004 point 3: a foreign-league season, or one older than
    MAX_SEASON_AGE relative to CURRENT_SEASON, must not be picked up as
    "the latest" — the whole point of the season/competition columns."""
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "New Arrival", "Como", "A", "PC", None)

    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        # More recent by season string, but not Serie A — must lose to the
        # older-but-Serie-A row below, not win on recency alone.
        {"season": "2025/26", "competition": "bundesliga_ger", "appearances": 20, "goals_scored": 8,
         "goals_conceded": None, "assists": 2, "avg_rating": 6.5, "yellow_cards": 1, "red_cards": 0},
        {"season": "2024/25", "competition": "serie_a", "appearances": 15, "goals_scored": 3,
         "goals_conceded": None, "assists": 1, "avg_rating": 6.1, "yellow_cards": 2, "red_cards": 0},
        # Real Serie A, but too old (CURRENT_SEASON 2026/27 - MAX_SEASON_AGE 2 = 2024) — dropped.
        {"season": "2018/19", "competition": "serie_a", "appearances": 30, "goals_scored": 10,
         "goals_conceded": None, "assists": 5, "avg_rating": 6.8, "yellow_cards": 0, "red_cards": 0},
    ], scraped_at="2026-08-27")

    result = repository.get_all_latest_player_season_stats(conn)

    assert result[player_id]["season"] == "2024/25"
    assert result[player_id]["competition"] == "serie_a"
    conn.close()


def test_get_all_latest_player_season_stats_keeps_rows_with_unknown_competition(tmp_path):
    """TASK-008/P0-004: a row with no competition label at all (every row
    written before this column existed) must still be picked up — only a
    row *explicitly* labeled non-Serie-A is excluded, so shipping this
    doesn't silently blank out the real DB's pre-existing season stats
    until they're naturally re-scraped."""
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "Legacy Row", "Como", "A", "PC", None)

    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2025/26", "appearances": 20, "goals_scored": 8, "goals_conceded": None,
         "assists": 2, "avg_rating": 6.5, "yellow_cards": 1, "red_cards": 0},
    ], scraped_at="2026-08-27")

    result = repository.get_all_latest_player_season_stats(conn)

    assert result[player_id]["season"] == "2025/26"
    assert result[player_id]["competition"] is None
    conn.close()


def test_get_all_player_set_pieces_groups_by_player(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "Calhanoglu", "Inter", "C", "M", None)

    repository.replace_player_set_pieces(conn, "fantacalcio_it", [
        (player_id, "rigori", 1, "2026-08-27"),
        (player_id, "punizioni", 1, "2026-08-27"),
    ])

    result = repository.get_all_player_set_pieces(conn)

    categories = {sp["category"] for sp in result[player_id]}
    assert categories == {"rigori", "punizioni"}
    conn.close()


def test_player_anagrafica_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)

    repository.upsert_player_anagrafica(
        conn, player_id, birth_date="2003-02-26", height_cm=184, foot="destro",
        nationality="Germania", shirt_number=10, updated_at="2026-08-27",
    )

    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["birth_date"] == "2003-02-26"
    assert profile["height_cm"] == 184
    assert profile["foot"] == "destro"
    assert profile["shirt_number"] == 10
    conn.close()


def test_player_anagrafica_get_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "No Profile", "Inter", "C", None, None)

    assert repository.get_player_anagrafica(conn, player_id) is None
    conn.close()


def test_player_anagrafica_upsert_overwrites_in_place(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)

    repository.upsert_player_anagrafica(
        conn, player_id, "2003-02-26", 184, "destro", "Germania", 10, "2026-08-01",
    )
    repository.upsert_player_anagrafica(
        conn, player_id, "2003-02-26", 184, "destro", "Germania", 42, "2026-08-27",
    )

    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["shirt_number"] == 42
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM player_anagrafica WHERE player_id = ?", (player_id,),
    ).fetchone()
    assert rows["n"] == 1
    conn.close()


def test_player_advanced_stats_insert_and_get_latest(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    repository.insert_player_advanced_stats(
        conn, player_id, xg90_percentile=53, xa90_percentile=43,
        shots90_percentile=22, key_passes90_percentile=63,
        involvement_percentile=34, minutes_percentile=43,
        source="fantanalisi", scrape_date="2026-08-27",
    )

    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    assert latest["xa90_percentile"] == 43
    conn.close()


def test_player_advanced_stats_get_latest_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "No Stats", "Inter", "A", None, None)

    assert repository.get_latest_player_advanced_stats(conn, player_id) is None
    conn.close()


def test_player_advanced_stats_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    repository.insert_player_advanced_stats(
        conn, player_id, 50, 40, 20, 60, 30, 40, "fantanalisi", "2026-08-20",
    )
    repository.insert_player_advanced_stats(
        conn, player_id, 53, 43, 22, 63, 34, 43, "fantanalisi", "2026-08-27",
    )

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM player_advanced_stats WHERE player_id = ?", (player_id,),
    ).fetchone()
    assert rows["n"] == 2
    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    conn.close()


def test_team_fixture_difficulty_insert_and_get_all_latest(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    repository.insert_team_fixture_difficulty(
        conn, "Venezia", difficulty_attack=65, difficulty_defense=58,
        window_label="prime 5 giornate", source="fantanalisi", scrape_date="2026-08-27",
    )

    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    assert latest["Venezia"]["difficulty_defense"] == 58
    conn.close()


def test_team_fixture_difficulty_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    repository.insert_team_fixture_difficulty(
        conn, "Venezia", 60, 55, "prime 5 giornate", "fantanalisi", "2026-08-20",
    )
    repository.insert_team_fixture_difficulty(
        conn, "Venezia", 65, 58, "prime 5 giornate", "fantanalisi", "2026-08-27",
    )

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM team_fixture_difficulty WHERE team = 'Venezia'",
    ).fetchone()
    assert rows["n"] == 2
    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    conn.close()


def test_player_fantanalisi_valuation_insert_and_get_latest(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", None, None)

    repository.insert_player_fantanalisi_valuation(
        conn, player_id, fair_price_range="≤168 · ≤216", max_bid="264",
        tier="1", risk="●", source="fantanalisi", scrape_date="2026-08-27",
    )

    latest = repository.get_latest_player_fantanalisi_valuation(conn, player_id)
    assert latest["fair_price_range"] == "≤168 · ≤216"
    assert latest["max_bid"] == "264"
    assert latest["tier"] == "1"
    assert latest["risk"] == "●"
    conn.close()


def test_player_fantanalisi_valuation_get_latest_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "No Valuation", "Inter", "A", None, None)

    assert repository.get_latest_player_fantanalisi_valuation(conn, player_id) is None
    conn.close()


def test_player_fantanalisi_valuation_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", None, None)

    repository.insert_player_fantanalisi_valuation(
        conn, player_id, "≤160 · ≤210", "250", "2", "●●", "fantanalisi", "2026-08-20",
    )
    repository.insert_player_fantanalisi_valuation(
        conn, player_id, "≤168 · ≤216", "264", "1", "●", "fantanalisi", "2026-08-27",
    )

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM player_fantanalisi_valuations WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    assert rows["n"] == 2
    latest = repository.get_latest_player_fantanalisi_valuation(conn, player_id)
    assert latest["tier"] == "1"
    conn.close()


def test_get_all_player_notes_bulk_read(tmp_path):
    """Bulk notes read used by the role pages: one query for the whole table,
    not one query per player (N+1 audit fix)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Calhanoglu", "Inter", "C", "M", None)
    other_id = repository.upsert_player(conn, "Dimarco", "Inter", "D", "Ds", None)

    repository.upsert_player_notes(conn, player_id, "rischia squalifica", "2026-08-27")

    assert repository.get_all_player_notes(conn) == {player_id: "rischia squalifica"}
    assert repository.get_player_notes(conn, other_id) is None
    conn.close()



def _insert_price(conn, player_id, source, scrape_date, price_current):
    """Only price_current matters for the ceiling; the rest of the row is
    what a source with no stats for this player would write."""
    repository.insert_quotation(
        conn, player_id, source, scrape_date, price_current=price_current,
        price_initial=None, status=None, fantamedia=None, avg_rating=None,
        appearances=None,
    )


def test_get_source_price_ceiling_returns_each_sources_highest_price(tmp_path):
    """The per-source calibration point compute_source_scale_factors rescales
    on is the source's own maximum, per source and independent of how many
    rows that source has — not a percentile, which meant a different rank
    ("3rd highest" vs "7th highest") depending on the source's sample size
    and left the top readings above the ceiling they were rescaled onto."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    top = repository.upsert_player(conn, "Malen", "Roma", "A", "Pu", None)
    mid = repository.upsert_player(conn, "Kean", "Fiorentina", "A", "Pu", None)
    cheap = repository.upsert_player(conn, "Piccoli", "Cagliari", "A", "Pu", None)

    _insert_price(conn, top, "fantanalisi", "2026-08-26", 382)
    _insert_price(conn, mid, "fantanalisi", "2026-08-26", 150)
    _insert_price(conn, cheap, "fantanalisi", "2026-08-26", 3)
    _insert_price(conn, top, "fantacalcio_online", "2026-08-26", 141.74)
    _insert_price(conn, mid, "fantacalcio_online", "2026-08-26", 90)
    # A price-less row must not count as a zero ceiling for its source.
    _insert_price(conn, cheap, "fantacalcio_online", "2026-08-26", None)

    ceilings = repository.get_source_price_ceiling(conn)

    assert ceilings == {"fantanalisi": 382, "fantacalcio_online": 141.74}
    conn.close()


def test_get_source_price_ceiling_uses_only_the_latest_scrape_per_source(tmp_path):
    """A stale scrape must not keep setting the scale: the ceiling comes from
    the same latest-row-per-source set every other consensus input uses
    (get_all_latest_quotations), so a price that has since come down doesn't
    permanently compress that source's scale."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Malen", "Roma", "A", "Pu", None)

    _insert_price(conn, player_id, "fantanalisi", "2026-08-01", 400)
    _insert_price(conn, player_id, "fantanalisi", "2026-08-26", 382)

    assert repository.get_source_price_ceiling(conn) == {"fantanalisi": 382}
    conn.close()
