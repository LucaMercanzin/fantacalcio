from playwright.sync_api import sync_playwright

from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.pianetafanta.it/quotazioni-fantacalcio"

TEAMS = [
    "ATALANTA", "BOLOGNA", "CAGLIARI", "COMO", "FIORENTINA", "FROSINONE",
    "GENOA", "INTER", "JUVENTUS", "LAZIO", "LECCE", "MILAN", "MONZA",
    "NAPOLI", "PARMA", "ROMA", "SASSUOLO", "TORINO", "UDINESE", "VENEZIA",
]


def _parse_price(text: str):
    text = text.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_team_rows(row_texts: list, team: str) -> list:
    """row_texts: list of [R, R1, GIOCATORE, QI, QA, +/-] cell-text rows for a
    single team (as returned by filtering the site's SQUADRE checkboxes to
    just that team, since the player-name cell has no separator between the
    surname and the embedded team name)."""
    records = []
    team_upper = team.upper()
    for cells in row_texts:
        if len(cells) < 5:
            continue
        role_classic, role_mantra, name_raw, qi_text, qa_text = cells[:5]

        name = name_raw.split(team_upper)[0].strip()
        if not name:
            continue

        records.append(PlayerRecord(
            name=name,
            team=team,
            role_classic=role_classic,
            role_mantra=role_mantra,
            price_current=_parse_price(qa_text),
            price_initial=_parse_price(qi_text),
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="pianetafanta",
        ))
    return records


def _dismiss_cookie_banner(page) -> None:
    try:
        page.wait_for_selector("#ez-cookie-dialog-wrapper", timeout=8000)
    except Exception:
        return
    # "accetta" (not "accetta tutto") keeps the default (mostly opted-out)
    # consent choices instead of opting in to everything.
    page.click("#ez-manage-settings")
    page.get_by_role("button", name="accetta", exact=True).click()
    page.wait_for_selector("#ez-cookie-dialog-wrapper", state="hidden", timeout=10000)


class PianetaFantaScraper(BaseScraper):
    def fetch(self) -> list:
        records = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(QUOTAZIONI_URL, timeout=30000)
            _dismiss_cookie_banner(page)

            for team in TEAMS:
                page.get_by_role("button", name="Deseleziona tutte").click()
                page.get_by_role("button", name=team, exact=True).click()
                page.get_by_role("button", name="CERCA", exact=True).click()
                page.wait_for_selector(".quot-results-table")

                row_texts = page.eval_on_selector_all(
                    ".quot-results-table tr",
                    "rows => rows.slice(1).map(r => "
                    "Array.from(r.cells).map(c => c.textContent.trim()))",
                )
                records.extend(parse_team_rows(row_texts, team))

            browser.close()
        return records
