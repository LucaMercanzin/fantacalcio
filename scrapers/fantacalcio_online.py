from bs4 import BeautifulSoup

from scrapers import base
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://api.fantacalcio-online.com/index.php/it/asta-fantacalcio-stima-prezzi"

# TASK-008/P0-004: the page's own footnote is explicit and unconditional —
# "M.V. è la media voto del 2025/2026" / "Pres. quante partite ha giocato"
# (verified against the live page 2026-08-30) — and for a player with no
# 2025/26 Serie A auction history at all ("NUOVO"), both cells are simply
# blank rather than falling back to a foreign league, so avg_rating/
# appearances here are always this exact season, always Serie A. Update
# this constant when the site rolls the page over to the next season.
STATS_SEASON = "2025/26"
STATS_COMPETITION = "serie_a"


def _parse_float(text: str):
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(text: str):
    text = text.strip()
    if not text.isdigit():
        return None
    return int(text)


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("table#players_list tbody tr"):
        role_span = row.select_one("td.player-pos span.role")
        team_td = row.select_one("td.team-name")
        name_td = row.select_one("td.player-name")
        value_tds = row.select("td.vote-col-no")

        if not (role_span and team_td and name_td) or len(value_tds) < 6:
            continue

        surname = name_td.select_one("span.text-bold")
        first_name = name_td.select_one("span.text-muted")
        name = " ".join(
            part.get_text(strip=True) for part in (surname, first_name) if part
        )

        _kap, _price_8_350, _price_10_350, price_8_500, _price_10_500, mv = value_tds[:6]
        appearances = value_tds[6] if len(value_tds) > 6 else None

        records.append(PlayerRecord(
            name=name,
            team=team_td.get_text(strip=True),
            role_classic=role_span.get_text(strip=True),
            role_mantra=None,
            # Prezzo medio osservato nelle aste reali per il formato 8
            # squadre / 500 crediti (la lega standard italiana classica), non
            # il "Kap." ufficiale: quest'ultimo è sulla stessa scala 1-40
            # delle quotazioni-listino delle altre fonti, mentre qui vogliamo
            # il credito realmente speso in asta.
            price_current=_parse_float(price_8_500.get_text()),
            price_initial=None,
            status=None,
            fantamedia=None,
            avg_rating=_parse_float(mv.get_text()),
            appearances=_parse_int(appearances.get_text()) if appearances is not None else None,
            photo_url=None,
            source="fantacalcio_online",
            stats_season=STATS_SEASON,
            stats_competition=STATS_COMPETITION,
        ))
    return records


class FantacalcioOnlineScraper(BaseScraper):
    def fetch(self) -> list:
        response = base.get(QUOTAZIONI_URL)
        return parse_html(response.text)
