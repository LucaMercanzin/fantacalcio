import os
from scrapers.fantacalciopedia import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalciopedia_sample.html"
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
