from db import repository
from db.connection import get_connection, init_db
from pipeline.run_player_anagrafica import run


def test_run_saves_anagrafica_for_matched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)
    repository.upsert_transfermarkt_id(conn, player_id, 580195, "2026-08-01")

    monkeypatch.setattr(
        "pipeline.run_player_anagrafica.fetch_player_profile",
        lambda tid: {
            "birth_date": "2003-02-26", "height_cm": 184, "foot": "destro",
            "nationality": "Germania", "shirt_number": 10,
        },
    )
    import pipeline.run_player_anagrafica as mod
    monkeypatch.setattr(mod, "REQUEST_DELAY_SECONDS", 0)

    result = run(conn)

    assert result["matched"] == 1
    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["height_cm"] == 184
    conn.close()


def test_run_skips_player_with_no_transfermarkt_match(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    repository.upsert_player(conn, "Nobody Real", "Inter", "C", None, None)

    monkeypatch.setattr(
        "pipeline.run_player_anagrafica.search_player_id", lambda name, team_hint=None: None,
    )
    import pipeline.run_player_anagrafica as mod
    monkeypatch.setattr(mod, "REQUEST_DELAY_SECONDS", 0)

    result = run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    conn.close()
