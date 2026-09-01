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
    def iter_many(self, detail_urls: list):
        """Come fetch_many, ma restituisce (detail_url, percentili) uno alla
        volta invece che tutto insieme alla fine.

        Esiste perché la versione "tutto insieme" ha un difetto che è costato
        davvero: ~500 pagine con Playwright sono decine di minuti, e finché il
        dizionario non era completo il chiamante non scriveva **niente** su
        database. Un'interruzione a metà — un Ctrl+C, la macchina che va in
        sospensione — buttava via l'intera scansione: `player_advanced_stats`
        è rimasta a 0 righe dopo 45 minuti di crawl (01/09/2026). Consumando
        il generatore, il chiamante può salvare mano a mano e ripartire da
        dove si era fermato invece che da capo.

        Un browser solo per tutto il batch, una navigazione per url."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            try:
                for detail_url in detail_urls:
                    try:
                        page.goto(f"{BASE_URL}{detail_url}", timeout=45000)
                        # state="attached", non il "visible" di default: un
                        # <title> dentro un <circle> SVG è un nodo di
                        # accessibilità/tooltip, non viene mai renderizzato, e
                        # quindi per Playwright non diventa mai visibile.
                        # L'attesa scadeva su *ogni* pagina — 45 minuti di
                        # crawl e zero righe scritte (01/09/2026) — mentre il
                        # dato era lì: verificato sulla pagina live di
                        # Dimarco, 38 `circle title` con i percentili giusti.
                        page.wait_for_selector(
                            "circle title", state="attached", timeout=15000,
                        )
                        titles = page.eval_on_selector_all(
                            "circle title", "els => els.map(e => e.textContent)",
                        )
                        yield detail_url, parse_percentile_titles(titles)
                    except Exception:
                        yield detail_url, None
            finally:
                # Anche se il consumatore smette a metà (GeneratorExit) il
                # browser va chiuso, o resta un chromium orfano per sessione
                # interrotta.
                browser.close()

    def fetch_many(self, detail_urls: list) -> dict:
        """detail_urls: PlayerRecord.detail_url values (relative paths like
        '/giocatori/10-kolo-muani'). Returns {detail_url: percentile dict or
        None on fetch failure} — one browser launch for the whole batch, one
        page navigation per url, matching the cost profile pipeline scripts
        already budget for per-record fetches (see run_fcp_metrics.py)."""
        return dict(self.iter_many(detail_urls))
