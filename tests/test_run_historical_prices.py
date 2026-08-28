from unittest.mock import patch

from db import repository
from db.connection import get_connection, init_db
from pipeline import run_historical_prices
from scrapers.base import PlayerRecord


def _record(name, team, price):
    return PlayerRecord(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=price, price_initial=price, status="ok", fantamedia=6.5,
        avg_rating=6.5, appearances=30, photo_url=None, source="fantacalcio_it",
    )


def test_run_imports_a_season_and_matches_by_team(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    with patch.object(run_historical_prices, "fetch_season_prices",
                       return_value=[_record("Lautaro Martinez", "Inter", 42)]):
        results = run_historical_prices.run(conn, seasons=["2024/25"])

    assert results["2024/25"]["matched"] == 1
    history = repository.get_price_history(conn, player_id)
    assert history == [{"source": "fantacalcio_it_storico", "scrape_date": "2024-08-01",
                         "price_current": 42.0}]
    conn.close()


def test_run_falls_back_to_any_team_match_for_transferred_player(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    # In the historical record he's still at his old (fictional) club
    with patch.object(run_historical_prices, "fetch_season_prices",
                       return_value=[_record("Lautaro Martinez", "Racing Club", 30)]):
        results = run_historical_prices.run(conn, seasons=["2018/19"])

    assert results["2018/19"]["matched"] == 1
    history = repository.get_price_history(conn, player_id)
    assert history[0]["price_current"] == 30.0
    conn.close()


def test_run_is_idempotent_for_the_same_season(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    with patch.object(run_historical_prices, "fetch_season_prices",
                       return_value=[_record("Lautaro Martinez", "Inter", 42)]):
        run_historical_prices.run(conn, seasons=["2024/25"])
        run_historical_prices.run(conn, seasons=["2024/25"])

    history = repository.get_price_history(conn, player_id)
    assert len(history) == 1
    conn.close()


def test_run_keeps_best_scoring_match_when_two_teammates_share_a_surname(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    # Two different real Inter players, both surnamed Martinez, both fuzzy
    # -match our single "Lautaro Martinez" row against a thin candidate pool.
    records = [
        _record("Martinez Jo.", "Inter", 8),
        _record("Martinez L.", "Inter", 26),
    ]
    with patch.object(run_historical_prices, "fetch_season_prices", return_value=records):
        results = run_historical_prices.run(conn, seasons=["2024/25"])

    assert results["2024/25"]["matched"] == 1
    history = repository.get_price_history(conn, player_id)
    assert len(history) == 1
    assert history[0]["price_current"] == 26.0
    conn.close()


def test_historical_rows_excluded_from_live_consensus(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)
    repository.insert_quotation(conn, player_id, "fantacalcio_it", "2026-08-24",
                                 38, 30, "ok", 7.0, 6.8, 30)

    with patch.object(run_historical_prices, "fetch_season_prices",
                       return_value=[_record("Lautaro Martinez", "Inter", 999)]):
        run_historical_prices.run(conn, seasons=["2020/21"])

    latest = repository.get_latest_quotations_for_player(conn, player_id)
    sources = {row["source"] for row in latest}
    assert sources == {"fantacalcio_it"}
    assert all(row["price_current"] != 999 for row in latest)
    conn.close()
