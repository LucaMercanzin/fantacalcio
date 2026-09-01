from datetime import date

import pipeline.run_player_advanced_stats as mod
from db import repository
from db.connection import get_connection, init_db
from scrapers.base import PlayerRecord


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
            "iter_many": lambda self, urls: iter([
                ("/giocatori/10-x", {
                    "xg90_percentile": 53, "xa90_percentile": 43,
                    "shots90_percentile": 22, "key_passes90_percentile": 63,
                    "involvement_percentile": 34, "minutes_percentile": 43,
                }),
            ]),
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 1
    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    conn.close()


def test_run_does_not_even_fetch_a_page_it_cannot_attribute(tmp_path, monkeypatch):
    """Il matching gira prima dello scraping: la pagina di un giocatore che
    non corrisponde a nessuna riga di `players` non viene proprio aperta.
    Prima veniva scaricata e poi scartata — una navigazione Playwright
    buttata per ogni nome non abbinato."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    fetched = []

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Nobody Real", "Inter", "/giocatori/1-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "iter_many": lambda self, urls: (fetched.extend(urls), iter([]))[1],
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    assert fetched == []
    conn.close()


def test_a_run_interrupted_halfway_resumes_instead_of_starting_over(tmp_path, monkeypatch):
    """Il motivo per cui questo runner scrive mano a mano invece che alla
    fine: ~500 pagine Playwright sono decine di minuti, e il 01/09/2026
    un'interruzione a metà ha lasciato la tabella a zero righe. Chi è già
    stato scritto oggi non viene riletto."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    done_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)
    repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", None, None)
    repository.insert_player_advanced_stats(
        conn, done_id, 53, 43, 22, 63, 34, 43, "fantanalisi", date.today().isoformat(),
    )
    fetched = []

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [
                _record("Randal Kolo Muani", "Juventus", "/giocatori/10-x"),
                _record("Lautaro Martinez", "Inter", "/giocatori/11-y"),
            ],
        })(),
    )

    def _iter(self, urls):
        fetched.extend(urls)
        return iter([(u, {
            "xg90_percentile": 1, "xa90_percentile": 1, "shots90_percentile": 1,
            "key_passes90_percentile": 1, "involvement_percentile": 1,
            "minutes_percentile": 1,
        }) for u in urls])

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {"iter_many": _iter})(),
    )

    result = mod.run(conn)

    assert fetched == ["/giocatori/11-y"]  # la pagina già fatta non si riapre
    assert result == {"matched": 1, "skipped": 1, "failed": 0, "unmatched": []}
    # e il dato già scritto resta quello vero, non sovrascritto da 1
    assert repository.get_latest_player_advanced_stats(conn, done_id)["xg90_percentile"] == 53
    conn.close()


def test_a_failed_page_is_counted_not_swallowed(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Randal Kolo Muani", "Juventus", "/giocatori/10-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "iter_many": lambda self, urls: iter([("/giocatori/10-x", None)]),
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 0
    assert result["failed"] == 1
    conn.close()


def test_a_page_with_no_data_still_marks_the_player_as_done(tmp_path, monkeypatch):
    """fantanalisi pubblica "n.d." per i portieri e per chi non ha dati
    Understat: 188 righe su 505 sono tutte NULL, ed è corretto. Vanno scritte
    lo stesso, o la ripresa riaprirebbe quelle 188 pagine ogni volta."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Mile Svilar", "Roma", "P", None, None)
    empty = dict.fromkeys([
        "xg90_percentile", "xa90_percentile", "shots90_percentile",
        "key_passes90_percentile", "involvement_percentile", "minutes_percentile",
    ])

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Mile Svilar", "Roma", "/giocatori/40-svilar")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "iter_many": lambda self, urls: iter([("/giocatori/40-svilar", empty)]),
        })(),
    )

    assert mod.run(conn)["matched"] == 1
    assert player_id in mod._already_done_today(conn, date.today().isoformat())
    conn.close()
