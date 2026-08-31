import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from scrapers import base
from scrapers.base import BaseScraper, PlayerRecord

BASE_URL = "https://www.fantacalciopedia.com/lista-calciatori-serie-a"

ROLE_PATHS = {
    "P": "portieri",
    "D": "difensori",
    "C": "centrocampisti",
    "A": "attaccanti",
}


def parse_html(html: str, role_classic: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("div.col_full.giocatore"):
        name_el = row.select_one("h3.tit_calc")
        team_el = row.select_one("p small")
        photo_el = row.select_one("div.fbox-icon img")
        stats = row.select("span.stats_calc")

        if not name_el or not team_el:
            continue

        photo_url = photo_el["src"] if photo_el else None
        if photo_url and "puppet" in photo_url:
            photo_url = None

        link_el = name_el.find_parent("a")
        detail_url = link_el["href"] if link_el else None

        appearances = None
        fantamedia = None
        if len(stats) >= 1:
            text = stats[0].get_text(strip=True).replace("PRES.", "").strip()
            appearances = int(text) if text.isdigit() else None
        if len(stats) >= 2:
            text = stats[1].get_text(strip=True).replace("F.MEDIA", "").strip()
            try:
                value = float(text)
                # Fantacalciopedia shows "F.MEDIA 0" for players with no
                # Serie A fantamedia yet (new arrivals from abroad) — 0 is
                # its way of saying "no data", not a real average (P0-003).
                fantamedia = value if value > 0 else None
            except ValueError:
                fantamedia = None

        records.append(PlayerRecord(
            name=name_el.get_text(strip=True).title(),
            team=team_el.get_text(strip=True),
            role_classic=role_classic,
            role_mantra=None,
            price_current=None,
            price_initial=None,
            status=None,
            fantamedia=fantamedia,
            avg_rating=None,
            appearances=appearances,
            photo_url=photo_url,
            source="fantacalciopedia",
            detail_url=detail_url,
            # TASK-008/P0-004: this list page's PRES./F.MEDIA is *always*
            # Serie A (the URL itself is scoped to "lista-calciatori-serie-
            # a", and verified against the real site: the two players
            # checked who stayed in Serie A across two seasons never showed
            # a foreign-league fallback here). It is NOT always the *same*
            # season, though — it silently rolls from the current season's
            # matches to last season's once the current season has some,
            # with no visible label on this page saying which — verified by
            # comparing this page's live value against the season-labeled
            # detail page (scrapers.fantacalciopedia.parse_season_stats) for
            # the same player on the same day and finding it can match
            # either one depending on the player. stats_season stays None
            # rather than guessing; consensus/engine.py only filters on
            # stats_competition for this reason (see quotations.stats_season
            # comment in db/schema.sql).
            stats_season=None,
            stats_competition="serie_a",
        ))
    return records


@dataclass
class FcpDetail:
    alg_fcp: float | None = None
    punteggio_fcp: float | None = None
    investment_stability_pct: float | None = None
    injury_resistance_pct: float | None = None
    predicted_appearances: str | None = None
    predicted_goals: str | None = None
    predicted_assists: str | None = None
    skills: list = field(default_factory=list)
    season_stats: list = field(default_factory=list)


# The detail page embeds up to 3 seasons of actual (not predicted) stats as
# inline Chart.js data — "barChart"/"barChart2"/"barChart4" — rather than in
# a scrapeable <table>. Regex over the raw HTML instead of BeautifulSoup
# because the data lives inside a <script> block's JS object literal, not
# in tag attributes/text BeautifulSoup would expose. Newer/less established
# players simply have fewer than 3 blocks on the page — nothing to guard
# against beyond "however many matches there are".
#
# TASK-008/P0-004: the competition/club label (e.g. "Serie A" or "BundesLiga
# (GER)") sits in a <span class="stickpic bianco"> right after the season
# header and before the Chart.js block — verified against the real page
# (Malen Donyell: "Statistiche 2025-2026 ... Serie A ... Roma" then
# "Statistiche 2024-2025 ... BundesLiga (GER) ... Borussia Dortmund"),
# captured here instead of discarded so a season played abroad can be told
# apart from one played in Serie A.
SEASON_STATS_PATTERN = re.compile(
    r'Statistiche (\d{4})-(\d{4})\s+\S.*?'
    r'stickpic bianco">([^<]+)</span>.*?'
    r'labels:\s*\[([^\]]+)\].*?'
    r'data:\s*\[([^\]]+)\]',
    re.DOTALL,
)


def _normalize_competition(text: str) -> str:
    """"Serie A" -> "serie_a", "BundesLiga (GER)" -> "bundesliga_ger" — a
    plain slug, not a curated list of known leagues: the filter that matters
    (consensus/engine.py) only ever checks for the literal "serie_a" value,
    so any foreign league just needs to normalize to *something else*, not
    to a specific recognized code."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug


def parse_season_stats(html: str) -> list:
    """Season-by-season presenze/gol/assist/media voto/ammonizioni/espulsioni
    from the same detail page fetch_detail already retrieves for FCP
    metrics — adds zero extra HTTP requests to the existing (throttled)
    run_fcp_metrics crawl. The 2nd stat is "golF" (gol fatti) for outfield
    players but "golS" (gol subiti) for portieri — captured separately as
    goals_scored/goals_conceded rather than assumed, since they mean
    opposite things for a striker vs a goalkeeper.
    """
    seasons = []
    for start_year, end_year, raw_competition, raw_labels, raw_values in SEASON_STATS_PATTERN.findall(html):
        labels = [label.strip().strip('"\'') for label in raw_labels.split(",")]
        try:
            values = [float(v.strip()) for v in raw_values.split(",")]
        except ValueError:
            continue
        if len(labels) != len(values) or len(values) != 6:
            continue
        by_label = dict(zip(labels, values))

        seasons.append({
            "season": f"{start_year}/{end_year[-2:]}",
            "competition": _normalize_competition(raw_competition),
            "appearances": int(by_label.get("presenze", 0)),
            "goals_scored": int(by_label["golF"]) if "golF" in by_label else None,
            "goals_conceded": int(by_label["golS"]) if "golS" in by_label else None,
            "assists": int(by_label.get("ass", 0)),
            "avg_rating": by_label.get("MV") or None,
            "yellow_cards": int(by_label.get("amm", 0)),
            "red_cards": int(by_label.get("esp", 0)),
        })
    return seasons


# Maps the <span> label text inside ul.skills li[data-percent] to the
# FcpDetail field it fills — this list is the clean, numeric (0-100) source
# for these four metrics, unlike the duplicated "3 su 5" text elsewhere on
# the page.
SKILLS_LABEL_MAP = {
    "alg fcp": "alg_fcp",
    "punteggio fantacalciopedia": "punteggio_fcp",
    "solidità fantainvestimento": "investment_stability_pct",
    "resistenza infortuni": "injury_resistance_pct",
}


def parse_detail(html: str) -> FcpDetail:
    soup = BeautifulSoup(html, "html.parser")
    detail = FcpDetail()

    for li in soup.select("ul.skills li[data-percent]"):
        label_el = li.select_one("span")
        if not label_el:
            continue
        label = label_el.get_text(strip=True).lower()
        field_name = SKILLS_LABEL_MAP.get(label)
        if not field_name:
            continue
        try:
            setattr(detail, field_name, float(li["data-percent"]))
        except (KeyError, ValueError):
            pass

    for strong_el in soup.find_all("strong"):
        label = strong_el.get_text(strip=True).lower()
        if label not in ("presenze previste:", "gol previsti:", "assist previsti:"):
            continue
        value_el = strong_el.find_next("span", class_="stickdan")
        if not value_el:
            continue
        value = value_el.get_text(strip=True) or None
        if label == "presenze previste:":
            detail.predicted_appearances = value
        elif label == "gol previsti:":
            detail.predicted_goals = value
        elif label == "assist previsti:":
            detail.predicted_assists = value

    skills = []
    for span in soup.select("div.mc_hookEvolution span.stickdanpic"):
        text = span.get_text(strip=True)
        if text:
            skills.append(text)
    detail.skills = skills

    detail.season_stats = parse_season_stats(html)

    return detail


class FantaCalciopediaScraper(BaseScraper):
    def fetch(self) -> list:
        records = []
        session = base.build_session()
        for role_classic, path in ROLE_PATHS.items():
            response = base.get(f"{BASE_URL}/{path}/", session=session)
            records.extend(parse_html(response.text, role_classic))
        return records


def fetch_detail(url: str) -> FcpDetail:
    response = base.get(url)
    return parse_detail(response.text)
