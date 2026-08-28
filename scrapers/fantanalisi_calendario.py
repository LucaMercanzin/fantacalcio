"""Scraper per la difficoltà di calendario (finestra "prime 5 giornate",
scala 0-100: 0=più duro, 100=più morbido) esposta da
https://www.fantanalisi.it/calendario — complementare a
scrapers/fantanalisi_squadre.py.

La vista di default è un .card intitolato "Chi parte in discesa": un
<button> per squadra con il nome in <span class="truncate"> e il punteggio
in <span class="num"> — è la vista "per chi attacca" (morbidezza =
quanto concede l'avversario). Un secondo bottone "🧤 Per la porta" attiva
la vista "per la porta" (stesso shape, punteggi diversi). Solo la finestra
"prime 5 giornate" è scrappata qui — il dettaglio giornata-per-giornata
richiederebbe interazione per-squadra, fuori scope (vedi plan)."""

from datetime import date

from playwright.sync_api import sync_playwright

CALENDARIO_URL = "https://www.fantanalisi.it/calendario"

TEAM_ROW_SELECTOR = ".card button:has(span.num)"
DEFENSE_TOGGLE_SELECTOR = 'button:has-text("Per la porta")'


def parse_team_scores(rows: list) -> list:
    records = []
    for row in rows:
        team = (row.get("team") or "").strip()
        if not team:
            continue
        score_text = (row.get("score") or "").strip()
        score = int(score_text) if score_text.isdigit() else None
        records.append({"team": team, "score": score})
    return records


class FantanalisiCalendarioScraper:
    def _read_rows(self, page) -> list:
        return page.eval_on_selector_all(
            TEAM_ROW_SELECTOR,
            """buttons => buttons.map(b => ({
                team: (b.querySelector('span.truncate') || {}).textContent || '',
                score: (b.querySelector('span.num') || {}).textContent || ''
            }))""",
        )

    def fetch(self) -> dict:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(CALENDARIO_URL, timeout=45000)
            page.wait_for_selector(TEAM_ROW_SELECTOR, timeout=20000)

            attack_rows = self._read_rows(page)

            page.click(DEFENSE_TOGGLE_SELECTOR, timeout=10000)
            page.wait_for_timeout(1000)
            defense_rows = self._read_rows(page)

            browser.close()
        return {
            "attack": parse_team_scores(attack_rows),
            "defense": parse_team_scores(defense_rows),
        }


def save_fixture_difficulty(conn, attack_records: list, defense_records: list,
                             window_label: str = "prime 5 giornate",
                             source: str = "fantanalisi", scrape_date: str = None) -> int:
    from db import repository

    scrape_date = scrape_date or date.today().isoformat()
    defense_by_team = {r["team"]: r["score"] for r in defense_records}

    saved = 0
    for record in attack_records:
        repository.insert_team_fixture_difficulty(
            conn, record["team"], record["score"],
            defense_by_team.get(record["team"]), window_label, source, scrape_date,
        )
        saved += 1
    return saved
