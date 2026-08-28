from playwright.sync_api import sync_playwright

from scrapers.base import BaseScraper, PlayerRecord

GIOCATORI_URL = "https://www.fantanalisi.it/giocatori"

TABLE_SELECTOR = "table.w-full tbody tr"

# Colonne della tabella, nell'ordine in cui appaiono nel DOM (vedi thead della
# pagina): Mio, R, Nome, Status, Squadra, Qt, FVM, Fm att., Mv att., G+A,
# Pres, Prezzo, Aste live, Fasce affare, Max, Tier, Risk, Note.
COL_ROLE = 1
COL_NAME = 2
COL_TEAM = 4
COL_ASTE_LIVE = 12
COL_FASCE_AFFARE = 13
COL_MAX = 14
COL_TIER = 15
COL_RISK = 16


def _parse_price(text: str):
    """'Aste live': prezzo medio osservato nelle aste reali del formato
    utente ('numero secco' = misurato). Un '~' iniziale indica che è stimato
    dalla curva per mancanza di dati misurati, non un prezzo osservato: in
    quel caso non lo trattiamo come credito reale."""
    text = text.strip()
    if not text or text.startswith("~") or text in ("-", "—"):
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _cell_or_none(cells: list, index: int):
    """Testo grezzo della cella, o None se assente/vuota/placeholder ('-',
    '—') — nessuna normalizzazione ulteriore: 'Fasce affare'/'Max'/'Tier'/
    'Risk' sono valutazioni proprietarie del sito, salvate così come sono
    mostrate, non riparsate in numeri (formato non verificato dal vivo)."""
    if index >= len(cells):
        return None
    text = cells[index].strip()
    return text if text and text not in ("-", "—") else None


def parse_rows(row_texts: list, hrefs: list | None = None) -> list:
    hrefs = hrefs or [None] * len(row_texts)
    records = []
    for cells, href in zip(row_texts, hrefs):
        if len(cells) <= COL_ASTE_LIVE:
            continue
        role = cells[COL_ROLE].strip()
        name = cells[COL_NAME].strip()
        team = cells[COL_TEAM].strip()
        if not (role and name and team):
            continue

        records.append(PlayerRecord(
            name=name,
            team=team,
            role_classic=role,
            role_mantra=None,
            price_current=_parse_price(cells[COL_ASTE_LIVE]),
            price_initial=None,
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="fantanalisi",
            detail_url=href,
            fair_price_range=_cell_or_none(cells, COL_FASCE_AFFARE),
            max_bid=_cell_or_none(cells, COL_MAX),
            tier_fantanalisi=_cell_or_none(cells, COL_TIER),
            risk_fantanalisi=_cell_or_none(cells, COL_RISK),
        ))
    return records


class FantanalisiScraper(BaseScraper):
    def fetch(self) -> list:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(GIOCATORI_URL, timeout=45000)
            page.wait_for_selector(TABLE_SELECTOR, timeout=20000)

            row_texts = page.eval_on_selector_all(
                TABLE_SELECTOR,
                "rows => rows.map(r => Array.from(r.cells).map(c => c.textContent.trim()))",
            )
            hrefs = page.eval_on_selector_all(
                TABLE_SELECTOR,
                "rows => rows.map(r => { const a = r.querySelector('a[href^=\\\"/giocatori/\\\"]'); return a ? a.getAttribute('href') : null; })",
            )
            browser.close()
        return parse_rows(row_texts, hrefs)
