import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.gazzetta.it/fantacalcio/quotazioni"


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select("div.player-item"):
        img = item.select_one("img.player-photo")
        records.append(PlayerRecord(
            name=item.select_one("span.player-name").get_text(strip=True),
            team=item.select_one("span.player-team").get_text(strip=True),
            role_classic=item.get("data-role", ""),
            role_mantra=None,
            price_current=float(item.select_one("span.quotazione-attuale").get_text(strip=True)),
            price_initial=float(item.select_one("span.quotazione-iniziale").get_text(strip=True)),
            status=None,
            fantamedia=None,
            avg_rating=float(item.select_one("span.media-voto").get_text(strip=True)),
            appearances=None,
            photo_url=img["src"] if img else None,
            source="gazzetta",
        ))
    return records


class GazzettaScraper(BaseScraper):
    def fetch(self) -> list:
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
