from unittest.mock import patch
from db.connection import init_db, get_connection
from db import repository
from pipeline import run_match_ratings


FAKE_PAGE = {
    "giornata": 1,
    "season": "2026/27",
    "entries": [
        {"team": "Inter", "player_name": "Lautaro", "fantacalcio_player_id": 1,
         "role": "A", "voto": 7.0, "fantavoto": 8.5},
        {"team": "Roma", "player_name": "Nessuno Sconosciuto", "fantacalcio_player_id": 2,
         "role": "A", "voto": 6.0, "fantavoto": 6.0},
    ],
}


def test_run_stores_ratings_for_matched_players(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    with patch.object(run_match_ratings, "fetch_voti", return_value=FAKE_PAGE):
        result = run_match_ratings.run(conn)

    assert result["matched"] == 1
    assert len(result["unmatched"]) == 1
    ratings = repository.get_recent_match_ratings(conn, player_id)
    assert ratings[0]["giornata"] == 1
    assert ratings[0]["fantavoto"] == 8.5
    conn.close()


def test_run_upserts_without_wiping_other_giornate(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    with patch.object(run_match_ratings, "fetch_voti", return_value=FAKE_PAGE):
        run_match_ratings.run(conn)

    giornata_2 = dict(FAKE_PAGE)
    giornata_2["giornata"] = 2
    giornata_2["entries"] = [
        {"team": "Inter", "player_name": "Lautaro", "fantacalcio_player_id": 1,
         "role": "A", "voto": 6.0, "fantavoto": 6.0},
    ]
    with patch.object(run_match_ratings, "fetch_voti", return_value=giornata_2):
        run_match_ratings.run(conn)

    ratings = repository.get_recent_match_ratings(conn, player_id, limit=10)
    assert len(ratings) == 2
    assert {r["giornata"] for r in ratings} == {1, 2}
    conn.close()


def test_run_aborts_on_unparseable_page(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    with patch.object(run_match_ratings, "fetch_voti",
                       return_value={"giornata": None, "season": None, "entries": []}):
        result = run_match_ratings.run(conn)

    assert result["matched"] == 0
    assert result["skipped_reason"] == "unparseable_page"
    conn.close()
