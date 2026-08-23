import os
from scrapers.fantapazz import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantapazz_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 3
    assert not any(r.name == "Suzuki" for r in records)
    svilar = next(r for r in records if r.name == "Svilar")
    assert svilar.team == "ROM"
    assert svilar.role_classic == "P"
    assert svilar.price_current == 35.0
    assert svilar.source == "fantapazz"

    dimarco = next(r for r in records if r.name == "Dimarco")
    assert dimarco.team == "INT"
    assert dimarco.role_classic == "D"
    assert dimarco.price_current == 41.0
