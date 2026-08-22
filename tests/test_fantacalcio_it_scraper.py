import os
from scrapers.fantacalcio_it import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalcio_it_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 2
    lautaro = next(r for r in records if r.name == "Lautaro Martinez")
    assert lautaro.team == "Inter"
    assert lautaro.role_classic == "A"
    assert lautaro.price_current == 38
    assert lautaro.price_initial == 30
    assert lautaro.fantamedia == 6.8
    assert lautaro.status == "ok"
    assert lautaro.photo_url == "https://www.fantacalcio.it/img/players/12345.png"
    assert lautaro.source == "fantacalcio_it"
