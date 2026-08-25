from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup
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
                fantamedia = float(text)
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
        ))
    return records


@dataclass
class FcpDetail:
    alg_fcp: Optional[float] = None
    punteggio_fcp: Optional[float] = None
    investment_stability_pct: Optional[float] = None
    injury_resistance_pct: Optional[float] = None
    predicted_appearances: Optional[str] = None
    predicted_goals: Optional[str] = None
    predicted_assists: Optional[str] = None
    skills: list = field(default_factory=list)


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

    return detail


class FantaCalciopediaScraper(BaseScraper):
    def fetch(self) -> list:
        records = []
        for role_classic, path in ROLE_PATHS.items():
            response = requests.get(f"{BASE_URL}/{path}/", timeout=30)
            response.raise_for_status()
            records.extend(parse_html(response.text, role_classic))
        return records


def fetch_detail(url: str) -> FcpDetail:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return parse_detail(response.text)
