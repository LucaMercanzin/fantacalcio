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
    martinez = next(r for r in records if r.name == "Martinez L.")
    assert martinez.team == "INT"
    assert martinez.role_classic == "A"
    assert martinez.price_current == 38
    assert martinez.price_initial == 35
    assert martinez.source == "fantacalcio_it"

    sommer = next(r for r in records if r.name == "Sommer")
    assert sommer.role_classic == "P"
    assert sommer.price_current == 15
