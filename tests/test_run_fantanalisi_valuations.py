from db.connection import init_db, get_connection
from db import repository
from scrapers.base import PlayerRecord
import pipeline.run_fantanalisi_valuations as mod


def _record(name, team, **overrides):
    base = dict(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=None,
        avg_rating=None, appearances=None, photo_url=None, source="fantanalisi",
        fair_price_range="≤168 · ≤216", max_bid="264", tier_fantanalisi="1",
        risk_fantanalisi="●",
    )
    base.update(overrides)
    return PlayerRecord(**base)


def test_run_saves_valuations_for_matched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", None, None)

    monkeypatch.setattr(
        "pipeline.run_fantanalisi_valuations.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Donyell Malen", "Roma")],
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 1
    latest = repository.get_latest_player_fantanalisi_valuation(conn, player_id)
    assert latest["tier"] == "1"
    assert latest["max_bid"] == "264"
    conn.close()


def test_run_skips_unmatched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    monkeypatch.setattr(
        "pipeline.run_fantanalisi_valuations.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Nobody Real", "Inter")],
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    conn.close()
