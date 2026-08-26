from bs4 import BeautifulSoup
from scrapers import base
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.fantacalcio.it/quotazioni-fantacalcio"

ROLE_MAP = {"p": "P", "d": "D", "c": "C", "a": "A"}


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("tr.player-row"):
        role_span = row.select_one("th.player-role-classic span.role")
        name_span = row.select_one("th.player-name a.player-name span")
        team_td = row.select_one("td.player-team")
        price_initial_td = row.select_one("td.player-classic-initial-price")
        price_current_td = row.select_one("td.player-classic-current-price")

        if not (role_span and name_span and team_td):
            continue

        records.append(PlayerRecord(
            name=name_span.get_text(strip=True),
            team=team_td.get_text(strip=True),
            role_classic=ROLE_MAP.get(role_span.get("data-value", ""), ""),
            role_mantra=None,
            price_current=float(price_current_td.get_text(strip=True)) if price_current_td else None,
            price_initial=float(price_initial_td.get_text(strip=True)) if price_initial_td else None,
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="fantacalcio_it",
        ))
    return records


class FantacalcioItScraper(BaseScraper):
    def fetch(self) -> list:
        response = base.get(QUOTAZIONI_URL)
        return parse_html(response.text)


def season_to_url_slug(season: str) -> str:
    """'2024/25' -> '2024-25', matching the site's own URL scheme (found by
    watching what its season <select> does client-side, since there's no
    documented API)."""
    start, end = season.split("/")
    return f"{start}-{end}"


def fetch_season_prices(season: str) -> list:
    """Same page template as the live quotations page, just an older season
    (site archives back to 2015/16). Used for historical price charts, not
    for the live consensus — callers must not treat this as a current price."""
    url = f"{QUOTAZIONI_URL}/{season_to_url_slug(season)}"
    response = base.get(url)
    return parse_html(response.text)
