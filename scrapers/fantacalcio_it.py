import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.fantacalcio.it/quotazioni-fantacalcio"


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("tr.player-row"):
        img = row.select_one("td.photo img")
        records.append(PlayerRecord(
            name=row.select_one("td.name").get_text(strip=True),
            team=row.select_one("td.team").get_text(strip=True),
            role_classic=row.select_one("td.role").get_text(strip=True),
            role_mantra=None,
            price_current=float(row.select_one("td.price-current").get_text(strip=True)),
            price_initial=float(row.select_one("td.price-initial").get_text(strip=True)),
            status=row.select_one("td.status").get_text(strip=True),
            fantamedia=float(row.select_one("td.fantamedia").get_text(strip=True)),
            avg_rating=float(row.select_one("td.avg-rating").get_text(strip=True)),
            appearances=int(row.select_one("td.appearances").get_text(strip=True)),
            photo_url=img["src"] if img else None,
            source="fantacalcio_it",
        ))
    return records


class FantacalcioItScraper(BaseScraper):
    def fetch(self) -> list:
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
