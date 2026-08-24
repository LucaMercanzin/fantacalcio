import requests
from bs4 import BeautifulSoup

RIGORISTI_URL = "https://www.fantacalcio.it/rigoristi-serie-a"

CATEGORY_MAP = {
    "rigori": "rigori",
    "calci piazzati": "punizioni",
}


def parse_html(html: str) -> list:
    """Parses fantacalcio.it's penalty/free-kick taker hierarchy page.

    Returns one row per (team, category, player), ordered by rank within
    the category — the page itself encodes the hierarchy as list order, so
    rank is derived from position, not scraped as a labeled field."""
    soup = BeautifulSoup(html, "html.parser")
    entries = []

    for card in soup.select("div.team-card"):
        team_name_el = card.select_one(".team-name")
        if not team_name_el:
            continue
        team = team_name_el.get_text(strip=True)

        for col in card.select(".row.row-responsive > .col"):
            header = col.select_one("header")
            if not header:
                continue
            category = CATEGORY_MAP.get(header.get_text(strip=True).lower())
            if not category:
                continue

            for rank, li in enumerate(col.select("ol.pill-list li"), start=1):
                link = li.select_one("a.player-name")
                if not link or not link.get("href"):
                    continue
                name_span = link.select_one("span")
                player_name = name_span.get_text(strip=True) if name_span else link.get_text(strip=True)
                fantacalcio_id = link["href"].rstrip("/").split("/")[-1]
                if not fantacalcio_id.isdigit():
                    continue

                entries.append({
                    "team": team,
                    "category": category,
                    "rank": rank,
                    "player_name": player_name,
                    "fantacalcio_player_id": int(fantacalcio_id),
                })

    return entries


def fetch_rigoristi() -> list:
    response = requests.get(RIGORISTI_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return parse_html(response.text)
