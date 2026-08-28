"""Scraper per i dati di squadra (xG/xGA/PPDA, fonte Understat) esposti da
https://www.fantanalisi.it/squadre — non giocatori, complementare a
scrapers/fantanalisi.py (che scrappa /giocatori).

Ogni squadra è una <section class="card" id="..."> con:
  <h2>Nome Squadra</h2>
  ...
  <span title="...">xG <b>1.81</b></span>
  <span title="...">xGA <b>1.36</b></span>
  <span title="...">PPDA <b>10.6</b></span>

I tre <span title> con xG/xGA/PPDA compaiono insieme solo per le squadre con
storico Understat — una squadra neopromossa (nessuna stagione di Serie A
precedente) ha la sezione ma senza quel blocco: xg/xga/ppda restano None,
non vengono inventati.
"""

from datetime import date

from playwright.sync_api import sync_playwright

SQUADRE_URL = "https://www.fantanalisi.it/squadre"

SECTION_SELECTOR = "section.card[id]"


def _parse_float(text):
    if not text:
        return None
    text = text.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_sections(sections: list) -> list:
    """sections: [{"team": str, "stats": [str, ...]}, ...] — stats è la
    lista testuale dei valori <b> dentro gli span[title] dell'intestazione,
    nell'ordine xG, xGA, PPDA quando presenti (0 o 3 elementi)."""
    records = []
    for section in sections:
        team = (section.get("team") or "").strip()
        if not team:
            continue
        stats = section.get("stats") or []
        xg = _parse_float(stats[0]) if len(stats) > 0 else None
        xga = _parse_float(stats[1]) if len(stats) > 1 else None
        ppda = _parse_float(stats[2]) if len(stats) > 2 else None
        records.append({"team": team, "xg": xg, "xga": xga, "ppda": ppda})
    return records


class FantanalisiSquadreScraper:
    def fetch(self) -> list:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(SQUADRE_URL, timeout=45000)
            page.wait_for_selector(SECTION_SELECTOR, timeout=20000)

            sections = page.eval_on_selector_all(
                SECTION_SELECTOR,
                """sections => sections.map(s => ({
                    team: (s.querySelector('h2') || {}).textContent || '',
                    stats: Array.from(s.querySelectorAll('span[title] b'))
                        .map(b => b.textContent.trim())
                }))""",
            )
            browser.close()
        return parse_sections(sections)


def save_team_strength(conn, records: list, source: str = "fantanalisi",
                        scrape_date: str | None = None) -> int:
    """Salva i record (output di parse_sections/fetch) in team_strength.
    Storicizzato: una riga per (team, source, scrape_date), non overwrite
    del giorno precedente."""
    from db import repository

    scrape_date = scrape_date or date.today().isoformat()
    for record in records:
        repository.insert_team_strength(
            conn, record["team"], record["xg"], record["xga"], record["ppda"],
            source, scrape_date,
        )
    return len(records)
