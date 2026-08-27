from db.connection import init_db, get_connection
from db import repository


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


def test_upsert_player_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    id1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    id2 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    assert id1 == id2
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
