"""Live selector health checks (TASK-024/S9): the fixture-based scraper
tests only prove a parser still matches the markup as of the date recorded
at the top of each fixture (see fixtures/*.html) — they say nothing about
whether the live site has changed since. These fetch the real pages and
run the same parser, asserting loose structural invariants (some records
came back, with the fields a scrape actually needs) rather than exact
values, since real prices/ratings change constantly and aren't the point
here.

Excluded from the default run (pytest.ini: `addopts = -m "not live"`) —
they make real network requests to third-party sites and can fail for
reasons that have nothing to do with this code (the site being down, rate
limiting, a network hiccup), so they don't belong in every CI run. Opt in
explicitly: `pytest -m live tests/test_live_selectors.py`.
"""

import pytest

from scrapers.fantacalcio_it import FantacalcioItScraper
from scrapers.fantacalcio_online import FantacalcioOnlineScraper
from scrapers.fantacalciopedia import FantaCalciopediaScraper
from scrapers.fantapazz import FantapazzScraper
from scrapers.transfermarkt import search_player_id

pytestmark = pytest.mark.live


def test_fantacalcio_it_selectors_still_match_production():
    records = FantacalcioItScraper().fetch()

    assert len(records) > 100  # ~540 on a healthy run, well below any real outage
    sample = records[0]
    assert sample.name
    assert sample.role_classic in {"P", "D", "C", "A"}


def test_fantacalcio_online_selectors_still_match_production():
    records = FantacalcioOnlineScraper().fetch()

    assert len(records) > 100
    sample = records[0]
    assert sample.name
    assert sample.role_classic in {"P", "D", "C", "A"}


def test_fantapazz_selectors_still_match_production():
    records = FantapazzScraper().fetch()

    assert len(records) > 100
    sample = records[0]
    assert sample.name
    assert sample.role_classic in {"P", "D", "C", "A"}


def test_fantacalciopedia_selectors_still_match_production():
    records = FantaCalciopediaScraper().fetch()

    assert len(records) > 100
    sample = records[0]
    assert sample.name
    assert sample.role_classic in {"P", "D", "C", "A"}


def test_transfermarkt_search_selectors_still_match_production():
    # A well-known, currently-active player — if the search selectors
    # break, this returns None instead of raising.
    player_id = search_player_id("Lautaro Martinez", "Inter")

    assert player_id is not None
    assert player_id > 0
