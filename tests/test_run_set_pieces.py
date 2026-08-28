from unittest.mock import patch

from db import repository
from db.connection import get_connection, init_db
from pipeline import run_set_pieces

FAKE_ENTRIES = [
    {"team": "Inter", "category": "rigori", "rank": 1,
     "player_name": "Lautaro", "fantacalcio_player_id": 1},
    {"team": "Inter", "category": "rigori", "rank": 2,
     "player_name": "Thuram", "fantacalcio_player_id": 2},
    {"team": "Roma", "category": "punizioni", "rank": 1,
     "player_name": "Nessuno Sconosciuto", "fantacalcio_player_id": 3},
]


def test_run_matches_by_team_and_fuzzy_name(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    lautaro_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)
    thuram_id = repository.upsert_player(conn, "Thuram Marcus", "Inter", "A", None, None)

    with patch.object(run_set_pieces, "fetch_rigoristi", return_value=FAKE_ENTRIES):
        result = run_set_pieces.run(conn)

    assert result["matched"] == 2
    assert len(result["unmatched"]) == 1
    assert result["unmatched"][0]["player_name"] == "Nessuno Sconosciuto"

    lautaro_pieces = repository.get_player_set_pieces(conn, lautaro_id)
    assert lautaro_pieces == [{
        "category": "rigori", "rank": 1, "source": "fantacalcio_it_rigoristi",
        "updated_at": lautaro_pieces[0]["updated_at"],
    }]
    thuram_pieces = repository.get_player_set_pieces(conn, thuram_id)
    assert thuram_pieces[0]["rank"] == 2
    conn.close()


def test_run_replaces_previous_snapshot_from_same_source(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)

    with patch.object(run_set_pieces, "fetch_rigoristi", return_value=FAKE_ENTRIES[:1]):
        run_set_pieces.run(conn)
    assert len(repository.get_player_set_pieces(conn, player_id)) == 1

    # a re-crawl with a changed hierarchy (Lautaro drops off) should clear the old row
    with patch.object(run_set_pieces, "fetch_rigoristi", return_value=[]):
        run_set_pieces.run(conn)
    assert repository.get_player_set_pieces(conn, player_id) == []
    conn.close()
