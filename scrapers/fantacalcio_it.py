import requests
from bs4 import BeautifulSoup
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
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
