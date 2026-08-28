from unittest.mock import patch

from db import repository
from db.connection import get_connection, init_db
from pipeline import run_fcp_metrics
from scrapers.base import PlayerRecord
from scrapers.fantacalciopedia import FcpDetail

FAKE_RECORDS = [
    PlayerRecord(
        name="Martinez Lautaro", team="Inter", role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=8.0,
        avg_rating=None, appearances=30, photo_url=None, source="fantacalciopedia",
        detail_url="https://www.fantacalciopedia.com/.../martinez-lautaro.html",
    ),
    PlayerRecord(
        name="Nessuno Sconosciuto", team="Roma", role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=6.0,
        avg_rating=None, appearances=10, photo_url=None, source="fantacalciopedia",
        detail_url="https://www.fantacalciopedia.com/.../nessuno.html",
    ),
    PlayerRecord(
        name="No Link Player", team="Inter", role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=5.0,
        avg_rating=None, appearances=5, photo_url=None, source="fantacalciopedia",
        detail_url=None,
    ),
]

FAKE_DETAIL = FcpDetail(
    alg_fcp=97, punteggio_fcp=75, investment_stability_pct=60,
    injury_resistance_pct=60, predicted_appearances="30+",
    predicted_goals="12/15", predicted_assists="3/5",
    skills=["Titolare"],
)


def test_run_matches_and_saves_fcp_metrics(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    lautaro_id = repository.upsert_player(conn, "Martinez Lautaro", "Inter", "A", None, None)

    with patch.object(run_fcp_metrics.FantaCalciopediaScraper, "fetch", return_value=FAKE_RECORDS), \
         patch.object(run_fcp_metrics, "fetch_detail", return_value=FAKE_DETAIL), \
         patch.object(run_fcp_metrics.time, "sleep"):
        result = run_fcp_metrics.run(conn)

    # "No Link Player" has no detail_url (skipped before matching), and
    # "Nessuno Sconosciuto" doesn't match any known player.
    assert result["matched"] == 1
    assert result["unmatched"] == ["Nessuno Sconosciuto"]

    latest = repository.get_latest_fcp_metrics(conn, lautaro_id)
    assert latest["alg_fcp"] == 97
    assert latest["skills"] == ["Titolare"]
    conn.close()


def test_run_saves_season_stats_from_the_same_detail_fetch(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    lautaro_id = repository.upsert_player(conn, "Martinez Lautaro", "Inter", "A", None, None)

    detail_with_seasons = FcpDetail(
        alg_fcp=97, skills=[],
        season_stats=[
            {"season": "2025/26", "appearances": 35, "goals_scored": 10, "goals_conceded": None,
             "assists": 6, "avg_rating": 6.39, "yellow_cards": 2, "red_cards": 0},
        ],
    )

    with patch.object(run_fcp_metrics.FantaCalciopediaScraper, "fetch", return_value=FAKE_RECORDS[:1]), \
         patch.object(run_fcp_metrics, "fetch_detail", return_value=detail_with_seasons), \
         patch.object(run_fcp_metrics.time, "sleep"):
        run_fcp_metrics.run(conn)

    seasons = repository.get_player_season_stats(conn, lautaro_id)
    assert len(seasons) == 1
    assert seasons[0]["season"] == "2025/26"
    assert seasons[0]["goals_scored"] == 10
    conn.close()


def test_run_skips_player_when_detail_fetch_fails(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    lautaro_id = repository.upsert_player(conn, "Martinez Lautaro", "Inter", "A", None, None)

    with patch.object(run_fcp_metrics.FantaCalciopediaScraper, "fetch", return_value=FAKE_RECORDS[:1]), \
         patch.object(run_fcp_metrics, "fetch_detail", side_effect=Exception("boom")), \
         patch.object(run_fcp_metrics.time, "sleep"):
        result = run_fcp_metrics.run(conn)

    assert result["matched"] == 0
    assert repository.get_latest_fcp_metrics(conn, lautaro_id) is None
    conn.close()
