from db.connection import init_db, get_connection
from db import repository
from pipeline import run_injuries


def test_run_populates_injuries_for_new_player(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    monkeypatch.setattr(run_injuries, "search_player_id", lambda name, team: 326029)
    monkeypatch.setattr(
        run_injuries, "fetch_injuries",
        lambda tm_id: [{"season": "24/25", "injury_type": "Malato", "date_from": "26/02/2025",
                         "date_to": "03/03/2025", "days_out": 6, "matches_missed": 1}],
    )
    monkeypatch.setattr(run_injuries.time, "sleep", lambda s: None)

    run_injuries.run(conn)

    assert repository.get_transfermarkt_id(conn, player_id) == 326029
    injuries = repository.get_player_injuries(conn, player_id)
    assert len(injuries) == 1
    assert injuries[0]["injury_type"] == "Malato"
    conn.close()


def test_run_skips_lookup_when_id_already_known(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)
    repository.upsert_transfermarkt_id(conn, player_id, 326029, "2026-08-24")

    search_calls = []
    monkeypatch.setattr(
        run_injuries, "search_player_id",
        lambda name, team: search_calls.append(1) or 326029,
    )
    monkeypatch.setattr(run_injuries, "fetch_injuries", lambda tm_id: [])
    monkeypatch.setattr(run_injuries.time, "sleep", lambda s: None)

    run_injuries.run(conn)

    assert search_calls == []
    conn.close()
