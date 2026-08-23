import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

BASE_URL = "https://www.fantacalciopedia.com/lista-calciatori-serie-a"

ROLE_PATHS = {
    "P": "portieri",
    "D": "difensori",
    "C": "centrocampisti",
    "A": "attaccanti",
}


def parse_html(html: str, role_classic: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("div.col_full.giocatore"):
        name_el = row.select_one("h3.tit_calc")
        team_el = row.select_one("p small")
        photo_el = row.select_one("div.fbox-icon img")
        stats = row.select("span.stats_calc")

        if not name_el or not team_el:
            continue

        appearances = None
        fantamedia = None
        if len(stats) >= 1:
            text = stats[0].get_text(strip=True).replace("PRES.", "").strip()
            appearances = int(text) if text.isdigit() else None
        if len(stats) >= 2:
            text = stats[1].get_text(strip=True).replace("F.MEDIA", "").strip()
            try:
                fantamedia = float(text)
            except ValueError:
                fantamedia = None

        records.append(PlayerRecord(
            name=name_el.get_text(strip=True).title(),
            team=team_el.get_text(strip=True),
            role_classic=role_classic,
            role_mantra=None,
            price_current=None,
            price_initial=None,
            status=None,
            fantamedia=fantamedia,
            avg_rating=None,
            appearances=appearances,
            photo_url=photo_el["src"] if photo_el else None,
            source="fantacalciopedia",
        ))
    return records


class FantaCalciopediaScraper(BaseScraper):
    def fetch(self) -> list:
        records = []
        for role_classic, path in ROLE_PATHS.items():
            response = requests.get(f"{BASE_URL}/{path}/", timeout=30)
            response.raise_for_status()
            records.extend(parse_html(response.text, role_classic))
        return records
