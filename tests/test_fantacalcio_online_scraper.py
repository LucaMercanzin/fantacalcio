import os

from scrapers.fantacalcio_online import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalcio_online_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 2
    malen = next(r for r in records if "MALEN" in r.name)
    assert malen.name == "MALEN Donyell"
    assert malen.team == "Roma"
    assert malen.role_classic == "A"
    assert malen.price_current == 141.74
    assert malen.avg_rating == 6.72
    assert malen.appearances == 18
    assert malen.source == "fantacalcio_online"
    # TASK-008/P0-004: the site's own footnote declares avg_rating/
    # appearances as always 2025/26 Serie A — verified live 2026-08-30.
    assert malen.stats_season == "2025/26"
    assert malen.stats_competition == "serie_a"

    sommer = next(r for r in records if "SOMMER" in r.name)
    assert sommer.role_classic == "P"
    assert sommer.price_current == 28.00
    assert sommer.appearances == 33
