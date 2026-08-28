from db.connection import init_db, get_connection
from db import repository
from scrapers.base import PlayerRecord
import pipeline.run_player_advanced_stats as mod


def _record(name, team, detail_url):
    return PlayerRecord(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=None,
        avg_rating=None, appearances=None, photo_url=None, source="fantanalisi",
        detail_url=detail_url,
    )


def test_run_saves_advanced_stats_for_matched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Randal Kolo Muani", "Juventus", "/giocatori/10-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "fetch_many": lambda self, urls: {
                "/giocatori/10-x": {
                    "xg90_percentile": 53, "xa90_percentile": 43,
                    "shots90_percentile": 22, "key_passes90_percentile": 63,
                    "involvement_percentile": 34, "minutes_percentile": 43,
                },
            },
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 1
    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    conn.close()


def test_run_skips_unmatched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Nobody Real", "Inter", "/giocatori/1-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "fetch_many": lambda self, urls: {"/giocatori/1-x": {
                "xg90_percentile": 10, "xa90_percentile": 10, "shots90_percentile": 10,
                "key_passes90_percentile": 10, "involvement_percentile": 10,
                "minutes_percentile": 10,
            }},
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    conn.close()
