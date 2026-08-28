import pipeline.run_fixture_difficulty as mod
from db import repository
from db.connection import get_connection, init_db


def test_run_saves_attack_and_defense_scores(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    monkeypatch.setattr(
        "pipeline.run_fixture_difficulty.FantanalisiCalendarioScraper",
        lambda: type("S", (), {
            "fetch": lambda self: {
                "attack": [{"team": "Venezia", "score": 65}],
                "defense": [{"team": "Venezia", "score": 58}],
            },
        })(),
    )

    result = mod.run(conn)

    assert result["teams"] == 1
    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    assert latest["Venezia"]["difficulty_defense"] == 58
    conn.close()
