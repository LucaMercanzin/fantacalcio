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


import datetime as _dt


def _parse_birth_date(text: str):
    """'26/02/2003 (23)' -> '2003-02-26' (ISO), dropping the trailing age in
    parentheses — the age is derivable, storing it would drift stale."""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return _dt.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _parse_height_cm(text: str):
    """'1,84 m' -> 184."""
    match = re.search(r"(\d)[.,](\d{2})", text)
    if not match:
        return None
    return int(match.group(1)) * 100 + int(match.group(2))


def parse_player_profile(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    profile = {
        "birth_date": None, "height_cm": None, "foot": None,
        "nationality": None, "shirt_number": None,
    }

    birth_el = soup.select_one('span[itemprop="birthDate"]')
    if birth_el:
        profile["birth_date"] = _parse_birth_date(birth_el.get_text(strip=True))

    height_el = soup.select_one('span[itemprop="height"]')
    if height_el:
        profile["height_cm"] = _parse_height_cm(height_el.get_text(strip=True))

    nationality_el = soup.select_one('span[itemprop="nationality"]')
    if nationality_el:
        text = nationality_el.get_text(" ", strip=True)
        profile["nationality"] = text.split(",")[0].strip() if text else None

    shirt_el = soup.select_one("span.data-header__shirt-number")
    if shirt_el:
        match = re.search(r"\d+", shirt_el.get_text(strip=True))
        profile["shirt_number"] = int(match.group()) if match else None

    # "Piede:" non ha un itemprop dedicato — è una coppia label/valore nella
    # info-table generica: il label è un <span> con questo testo esatto, il
    # valore è lo <span> immediatamente successivo nello stesso genitore.
    for label in soup.select("span.info-table__content--regular"):
        if label.get_text(strip=True) == "Piede:":
            value_el = label.find_next_sibling("span", class_="info-table__content--bold")
            if value_el:
                profile["foot"] = value_el.get_text(strip=True)
            break

    return profile


def fetch_player_profile(transfermarkt_id: int) -> dict:
    """Anagrafica (età/altezza/piede/nazionalità/numero maglia) — stessa
    PROFILE_URL di fetch_photo_url ma fetch indipendente: pipeline separate
    per dominio dato (vedi run_injuries.py/run_photos), non condividono la
    response tra loro in questo codebase."""
    response = base.get(PROFILE_URL.format(id=transfermarkt_id))
    return parse_player_profile(response.text)
