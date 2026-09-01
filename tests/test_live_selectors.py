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
from scrapers.fantanalisi_giocatore import FantanalisiGiocatoreScraper
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


def test_fantanalisi_detail_radar_still_readable_in_production():
    """La pagina di dettaglio fantanalisi non era coperta qui, ed è proprio
    dove si è rotta: `wait_for_selector("circle title")` aspettava lo stato
    "visible" di default, ma un <title> dentro un <circle> SVG non viene mai
    renderizzato. L'attesa scadeva su ogni pagina e
    `player_advanced_stats` restava a zero righe dopo 45 minuti di crawl
    (01/09/2026), senza che nessun test lo notasse."""
    results = FantanalisiGiocatoreScraper().fetch_many(["/giocatori/5-dimarco"])

    percentiles = results["/giocatori/5-dimarco"]
    assert percentiles is not None, "la pagina non ha restituito nessun percentile"
    # Almeno le due metriche portanti del radar devono arrivare valorizzate:
    # tutte a None significherebbe che il parser gira ma non legge più niente.
    assert percentiles["xg90_percentile"] is not None
    assert percentiles["minutes_percentile"] is not None
    assert all(
        v is None or 0 <= v <= 100 for v in percentiles.values()
    ), percentiles
