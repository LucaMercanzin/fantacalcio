import re
from bs4 import BeautifulSoup
from scrapers import base

VOTI_URL = "https://www.fantacalcio.it/voti-fantacalcio-serie-a"

ROLE_MAP = {"p": "P", "d": "D", "c": "C", "a": "A"}

TITLE_PATTERN = re.compile(r"Serie A (\d+)\D+giornata\D+stagione (\d{4}/\d{2})")


# Real grades are "5", "6,5", "7,5"... (comma decimal, plausibly 0-15 with
# bonuses). The page also emits bare two-digit values like "55"/"56" for some
# rows (observed on real data) with no comma and no documented meaning —
# rather than guess whether that means 5.5 or something else, we discard
# anything outside a plausible grade range instead of silently mis-scaling it.
_MAX_PLAUSIBLE_GRADE = 15


def _parse_grade(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = float(value.replace(",", "."))
    except ValueError:
        return None
    if not (0 <= parsed <= _MAX_PLAUSIBLE_GRADE):
        return None
    return parsed


def parse_html(html: str) -> dict:
    """Parses fantacalcio.it's match-by-match ratings page.

    Only the "Redazione Fantacalcio" column (the first vote pill) is kept —
    the page also shows "Voto Statistico" and "Voto Italia" columns, but
    those are a different editorial choice we're not trying to reproduce.

    Returns {"giornata": int, "season": str, "entries": [...]}. `giornata`
    and `season` are None if the title doesn't match the expected pattern
    (e.g. the page changed), so callers can decide whether to trust the
    data rather than silently storing it under a wrong matchday."""
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text() if soup.title else ""
    match = TITLE_PATTERN.search(title)
    giornata = int(match.group(1)) if match else None
    season = match.group(2) if match else None

    entries = []
    for block in soup.select("li.team-table"):
        team_el = block.select_one(".team-info .team-name")
        if not team_el:
            continue
        team = team_el.get_text(strip=True)

        for row in block.select("table.grades-table tbody tr"):
            link = row.select_one("a.player-name")
            if not link or not link.get("href"):
                continue
            fantacalcio_id = link["href"].rstrip("/").split("/")[-1]
            if not fantacalcio_id.isdigit():
                continue
            name_span = link.select_one("span")
            player_name = name_span.get_text(strip=True) if name_span else link.get_text(strip=True)

            role_span = row.select_one("span.role")
            role = ROLE_MAP.get(role_span.get("data-value", ""), "") if role_span else ""

            first_pill = row.select_one("td .group .pill")
            voto = fantavoto = None
            if first_pill:
                grade_el = first_pill.select_one(".player-grade")
                fanta_el = first_pill.select_one(".player-fanta-grade")
                voto = _parse_grade(grade_el.get("data-value")) if grade_el else None
                fantavoto = _parse_grade(fanta_el.get("data-value")) if fanta_el else None

            entries.append({
                "team": team,
                "player_name": player_name,
                "fantacalcio_player_id": int(fantacalcio_id),
                "role": role,
                "voto": voto,
                "fantavoto": fantavoto,
            })

    return {"giornata": giornata, "season": season, "entries": entries}


def fetch_voti() -> dict:
    response = base.get(VOTI_URL)
    return parse_html(response.text)
