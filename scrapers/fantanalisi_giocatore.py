"""Scraper per i percentili per-90 (xG/xA/tiri/rifiniture/coinvolgimento/
minuti) esposti sulla pagina di dettaglio giocatore di
https://www.fantanalisi.it/giocatori/{id}-{slug} — complementare a
scrapers/fantanalisi.py (che scrappa la sola tabella /giocatori).

Ogni pagina renderizza un radar SVG con un <circle> per metrica; il valore
percentile è nel testo del suo <title> figlio, formato
"{Nome} — {Metrica}: {N}° percentile" (verificato live sulla pagina di
Randal Kolo Muani, id 10). Solo il radar del giocatore stesso ha circle con
"percentile" nel title — un eventuale overlay di confronto ruolo condivide
lo stesso <svg> senza aggiungere circle/title propri.
"""

import re

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.fantanalisi.it"

# Etichette esatte usate dal sito per ciascuna metrica del radar -> colonna
# player_advanced_stats corrispondente.
METRIC_KEY_MAP = {
    "xG/90": "xg90_percentile",
    "xA/90": "xa90_percentile",
    "Tiri/90": "shots90_percentile",
    "Rifin.": "key_passes90_percentile",
    "Coinv.": "involvement_percentile",
    "Minuti": "minutes_percentile",
}

TITLE_PATTERN = re.compile(r"([A-Za-zÀ-ÿ0-9./]+):\s*(\d+)°?\s*percentile")


def parse_percentile_titles(titles: list) -> dict:
    result = {key: None for key in METRIC_KEY_MAP.values()}
    for title in titles or []:
        match = TITLE_PATTERN.search(title)
        if not match:
            continue
        key = METRIC_KEY_MAP.get(match.group(1).strip())
        if key:
            result[key] = int(match.group(2))
    return result


class FantanalisiGiocatoreScraper:
    def fetch_many(self, detail_urls: list) -> dict:
        """detail_urls: PlayerRecord.detail_url values (relative paths like
        '/giocatori/10-kolo-muani'). Returns {detail_url: percentile dict or
        None on fetch failure} — one browser launch for the whole batch, one
        page navigation per url, matching the cost profile pipeline scripts
        already budget for per-record fetches (see run_fcp_metrics.py)."""
        results = {}
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            for detail_url in detail_urls:
                try:
                    page.goto(f"{BASE_URL}{detail_url}", timeout=45000)
                    page.wait_for_selector("circle title", timeout=15000)
                    titles = page.eval_on_selector_all(
                        "circle title", "els => els.map(e => e.textContent)",
                    )
                    results[detail_url] = parse_percentile_titles(titles)
                except Exception:
                    results[detail_url] = None
            browser.close()
        return results
