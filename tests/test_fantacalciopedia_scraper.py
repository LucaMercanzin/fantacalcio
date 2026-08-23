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
    assert lautaro.photo_url == "https://www.fantacalciopedia.com/dnadmin/cms_files/calciatori/puppet/n05.png"
    assert lautaro.source == "fantacalciopedia"
