import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Some sources (e.g. fantacalcio.it's live quotations page) behave
# differently, or block outright, for a request with no/a bare-Python User-
# Agent — every scraper used to set its own (or none at all, inconsistently:
# fantacalcio_it.py's live-quotations fetch had none while its historical-
# season fetch did). One realistic desktop-Chrome UA, shared, so that
# inconsistency can't silently vary source data quality by scraper.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9",
}
DEFAULT_TIMEOUT = 30

# A source that 500s or times out once shouldn't drop out of that day's
# scraping run entirely — run_scraping.run_pipeline only logs and skips a
# scraper that raises, so a single flaky request meant losing that source
# until the next scheduled run. Retries only transient failures (connection
# errors, timeouts, 429/5xx) with exponential backoff; a real 404 or a
# malformed-HTML parse error still surfaces immediately, unretried.
RETRY = Retry(
    total=3, backoff_factor=1.0,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)


def build_session() -> requests.Session:
    """Session with the shared User-Agent/headers and retry/backoff applied
    to every request made through it. Scrapers that issue several requests
    (pagination, per-player detail pages) should build one session and reuse
    it, so the automatic retries build on top of connection pooling instead
    of establishing a fresh connection every attempt."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    adapter = HTTPAdapter(max_retries=RETRY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get(url: str, session: requests.Session = None, timeout: int = DEFAULT_TIMEOUT,
        **kwargs) -> requests.Response:
    """GET through the shared retry/backoff/User-Agent session, raising on a
    non-2xx status same as a bare requests.get(...).raise_for_status() would.
    Pass an explicit `session` (from build_session()) to reuse connections
    and retry state across multiple calls; omitted, a one-off session is used
    for this single request."""
    owned_session = session or build_session()
    try:
        response = owned_session.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    finally:
        if session is None:
            owned_session.close()


@dataclass
class PlayerRecord:
    name: str
    team: str
    role_classic: str
    role_mantra: str | None
    price_current: float | None
    price_initial: float | None
    status: str | None
    fantamedia: float | None
    avg_rating: float | None
    appearances: int | None
    photo_url: str | None
    source: str
    detail_url: str | None = None
    # Valutazioni proprietarie di fantanalisi.it (Fasce affare/Max/Tier/Risk,
    # colonne 13-16 della tabella /giocatori) — informative, non riusate nei
    # calcoli interni del progetto (ranking/scorer.py, tiers.py, verdict.py
    # hanno i propri equivalenti). Solo fantanalisi.py le popola.
    fair_price_range: str | None = None
    max_bid: str | None = None
    tier_fantanalisi: str | None = None
    risk_fantanalisi: str | None = None


class BaseScraper(ABC):
    @abstractmethod
    def fetch(self) -> list:
        ...
