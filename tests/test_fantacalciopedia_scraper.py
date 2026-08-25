import os
from scrapers.fantacalciopedia import parse_html, parse_detail

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
