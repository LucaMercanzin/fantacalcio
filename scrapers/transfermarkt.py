import re
from bs4 import BeautifulSoup
from scrapers import base

SEARCH_URL = "https://www.transfermarkt.it/schnellsuche/ergebnis/schnellsuche"
INJURIES_URL = "https://www.transfermarkt.it/-/verletzungen/spieler/{id}"


def _search_candidates(query: str) -> list:
    response = base.get(SEARCH_URL, params={"query": query})
    soup = BeautifulSoup(response.text, "html.parser")

    candidates = []
    for link in soup.select('a[href*="/profil/spieler/"]'):
        match = re.search(r"/profil/spieler/(\d+)", link.get("href", ""))
        if not match:
            continue
        row_text = link.find_parent("tr")
        row_text = row_text.get_text(" ", strip=True) if row_text else ""
        candidates.append((int(match.group(1)), row_text))
    return candidates


def search_player_id(name: str, team_hint: str = None) -> int:
    """Look up a player's Transfermarkt id via the quick-search endpoint.
    Returns the first result's id, or None if nothing matches. team_hint
    (if given) is used only to prefer a result whose row text mentions it,
    to reduce mismatches on common surnames.

    Our canonical names are "Surname[s] Firstname" (e.g. "Di Gregorio
    Michele") — Transfermarkt's search returns *zero* results for the full
    "surname firstname" string in that order, but matches reliably on the
    surname alone (or "firstname surname"), so that's tried first and the
    full string only as a fallback for names it does happen to accept."""
    tokens = name.split()
    surname = " ".join(tokens[:-1]) if len(tokens) > 1 else name

    candidates = _search_candidates(surname)
    if not candidates:
        candidates = _search_candidates(name)

    if not candidates:
        return None

    if team_hint:
        for player_id, row_text in candidates:
            if team_hint.lower() in row_text.lower():
                return player_id

    return candidates[0][0]


PROFILE_URL = "https://www.transfermarkt.it/-/profil/spieler/{id}"


def fetch_photo_url(transfermarkt_id: int) -> str:
    """Foto profilo ufficiale del giocatore (meta og:image della pagina
    profilo) — molto più affidabile della ricerca per nome su Wikipedia,
    che spesso non trova un calciatore o trova la persona sbagliata."""
    response = base.get(PROFILE_URL.format(id=transfermarkt_id))
    soup = BeautifulSoup(response.text, "html.parser")
    meta = soup.select_one('meta[property="og:image"]')
    return meta.get("content") if meta else None


def _parse_days(text: str):
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def parse_injuries(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.items")
    if not table:
        return []

    records = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        season = cells[0].get_text(strip=True)
        injury_type = cells[1].get_text(strip=True)
        date_from = cells[2].get_text(strip=True)
        date_to = cells[3].get_text(strip=True)
        days_out = _parse_days(cells[4].get_text(strip=True))
        matches_span = cells[5].select_one("span")
        matches_missed = int(matches_span.get_text(strip=True)) if matches_span and matches_span.get_text(strip=True).isdigit() else None

        records.append({
            "season": season,
            "injury_type": injury_type,
            "date_from": date_from,
            "date_to": date_to,
            "days_out": days_out,
            "matches_missed": matches_missed,
        })
    return records


def fetch_injuries(transfermarkt_id: int) -> list:
    response = base.get(INJURIES_URL.format(id=transfermarkt_id))
    return parse_injuries(response.text)
