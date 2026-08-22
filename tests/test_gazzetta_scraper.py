import os
from scrapers.gazzetta import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "gazzetta_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 2
    lautaro = next(r for r in records if r.name == "Lautaro Martinez")
    assert lautaro.team == "Inter"
    assert lautaro.role_classic == "A"
    assert lautaro.price_current == 37
    assert lautaro.price_initial == 29
    assert lautaro.avg_rating == 6.7
    assert lautaro.photo_url == "https://www.gazzetta.it/img/players/lautaro.png"
    assert lautaro.source == "gazzetta"
