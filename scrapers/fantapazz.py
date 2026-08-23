import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.fantapazz.com/fantacalcio/listone-e-quotazioni"


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("table.card tbody tr"):
        role_span = row.select_one("span.Ruolo")
        name_td = row.select_one("td.Calciatore")
        price_td = row.select_one("td.Quotazione")
        team_td = row.select_one("td.Club")

        if not (role_span and name_td and team_td):
            continue

        team = team_td.get_text(strip=True)
        if not team:
            continue

        price_text = price_td.get_text(strip=True) if price_td else ""
        records.append(PlayerRecord(
            name=name_td.get_text(strip=True),
            team=team,
            role_classic=role_span.get_text(strip=True),
            role_mantra=None,
            price_current=float(price_text) if price_text.replace(".", "", 1).isdigit() else None,
            price_initial=None,
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="fantapazz",
        ))
    return records


class FantapazzScraper(BaseScraper):
    def fetch(self) -> list:
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
