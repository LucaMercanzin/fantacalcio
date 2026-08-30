import os

from scrapers.fantacalciopedia import parse_detail, parse_html, parse_season_stats
from scrapers.fantacalciopedia import _normalize_competition

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalciopedia_sample.html"
)
DETAIL_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalciopedia_detail_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html, role_classic="A")

    assert len(records) == 2
    lautaro = next(r for r in records if r.name == "Martinez Lautaro")
    assert lautaro.team == "Inter"
    assert lautaro.role_classic == "A"
    assert lautaro.appearances == 30
    assert lautaro.fantamedia == 8.25
    assert lautaro.photo_url is None
    # TASK-008/P0-004: this page is scoped to Serie A rosters (verified live
    # 2026-08-30), but which exact season it's showing isn't labeled here.
    assert lautaro.stats_competition == "serie_a"
    assert lautaro.stats_season is None
    assert lautaro.source == "fantacalciopedia"


def test_parse_html_extracts_detail_url():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html, role_classic="A")

    lautaro = next(r for r in records if r.name == "Martinez Lautaro")
    assert lautaro.detail_url == (
        "https://www.fantacalciopedia.com/lista-calciatori-serie-a/"
        "attaccanti/2764/martinez-lautaro.html"
    )


def test_parse_detail_extracts_skills_metrics():
    with open(DETAIL_FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    detail = parse_detail(html)

    assert detail.alg_fcp == 97.0
    assert detail.punteggio_fcp == 75.0
    assert detail.investment_stability_pct == 60.0
    assert detail.injury_resistance_pct == 60.0
    assert detail.predicted_appearances == "30+"
    assert detail.predicted_goals == "12/15"
    assert detail.predicted_assists == "3/5"
    assert detail.skills == ["Outsider", "Titolare", "Goleador", "Rigorista"]


def test_parse_detail_handles_missing_fields():
    detail = parse_detail("<html><body></body></html>")

    assert detail.alg_fcp is None
    assert detail.punteggio_fcp is None
    assert detail.investment_stability_pct is None
    assert detail.injury_resistance_pct is None
    assert detail.predicted_appearances is None
    assert detail.predicted_goals is None
    assert detail.predicted_assists is None
    assert detail.skills == []


def test_parse_detail_includes_season_stats():
    with open(DETAIL_FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    detail = parse_detail(html)

    assert len(detail.season_stats) == 2
    latest = detail.season_stats[0]
    assert latest["season"] == "2025/26"
    assert latest["appearances"] == 35
    assert latest["goals_scored"] == 10
    assert latest["goals_conceded"] is None
    assert latest["assists"] == 6
    assert latest["avg_rating"] == 6.39
    assert latest["yellow_cards"] == 2
    assert latest["red_cards"] == 0
    assert detail.season_stats[1]["season"] == "2024/25"
    assert detail.season_stats[1]["appearances"] == 32


def test_parse_detail_season_stats_capture_the_competition():
    """TASK-008/P0-004: a season played abroad must be told apart from one
    played in Serie A — verified against the real page (Malen Donyell shows
    "Statistiche 2025-2026 ... Serie A ... Roma" then "Statistiche 2024-2025
    ... BundesLiga (GER) ... Borussia Dortmund")."""
    with open(DETAIL_FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    detail = parse_detail(html)

    assert detail.season_stats[0]["competition"] == "serie_a"


def test_normalize_competition_slugifies_a_foreign_league_name():
    assert _normalize_competition("Serie A") == "serie_a"
    assert _normalize_competition("BundesLiga (GER)") == "bundesliga_ger"


def test_parse_season_stats_uses_goals_conceded_for_goalkeepers():
    html = """
    <h4 class="panel-title">Statistiche 2025-2026 TEST KEEPER<br />
        <span class="stickpic bianco">Serie A</span></h4>
    <script>
    data: {
        labels: ["presenze","golS","ass","MV","amm","esp"],
        datasets: [{ data: [37,35,0,6.36,0,0] }]
    }
    </script>
    """
    seasons = parse_season_stats(html)

    assert len(seasons) == 1
    assert seasons[0]["goals_conceded"] == 35
    assert seasons[0]["goals_scored"] is None


def test_parse_season_stats_empty_when_no_charts_present():
    assert parse_season_stats("<html><body></body></html>") == []


def test_parse_html_keeps_real_photo_url():
    html = """
    <div class="col_full giocatore">
        <h3 class="tit_calc">Test Player</h3>
        <p><small>Test Team</small></p>
        <div class="fbox-icon"><img src="https://www.fantacalciopedia.com/dnadmin/cms_files/calciatori/reali/foo.jpg" alt=""></div>
        <span class="stats_calc">10 PRES.</span>
        <span class="stats_calc">6.50 F.MEDIA</span>
    </div>
    """
    records = parse_html(html, role_classic="A")
    assert records[0].photo_url == "https://www.fantacalciopedia.com/dnadmin/cms_files/calciatori/reali/foo.jpg"
