"""Serie A 2026/27 roster — USER-VERIFIED ground truth.

Venezia/Frosinone/Monza are the promoted side for 2026/27 (confirmed by the
project owner and docs/superpowers/plans/2026-08-27-portieri-depth-chart.md).
Cremonese/Pisa/Verona are NOT in this season's Serie A. The opus review's
"P0-006" claimed the opposite and nearly regressed the dashboard twice: this
test exists so the verified roster can't be silently swapped again.

Every list in the codebase that enumerates the 20 Serie A clubs must agree:
- dashboard/data_access.py  (TEAM_ABBREV_TO_FULL, PROMOTED_TEAMS)
- scrapers/pianetafanta.py  (TEAMS used for per-team scraping)
- db/schema.sql             (teams table)
"""

import sqlite3

from dashboard.data_access import (
    PROMOTED_TEAM_CODES,
    PROMOTED_TEAMS,
    TEAM_ABBREV_TO_FULL,
    is_current_serie_a_team,
)
from db.connection import init_db
from scrapers.pianetafanta import TEAMS

CURRENT_SERIE_A = {
    "Atalanta", "Bologna", "Cagliari", "Como", "Fiorentina", "Frosinone",
    "Genoa", "Inter", "Juventus", "Lazio", "Lecce", "Milan", "Monza",
    "Napoli", "Parma", "Roma", "Sassuolo", "Torino", "Udinese", "Venezia",
}
PROMOTED = {"Venezia", "Frosinone", "Monza"}
NOT_IN_SERIE_A = {"Cremonese", "Pisa", "Verona"}


def test_data_access_has_verified_2026_27_roster():
    assert set(TEAM_ABBREV_TO_FULL.values()) == CURRENT_SERIE_A
    assert "FRO" in TEAM_ABBREV_TO_FULL and "MON" in TEAM_ABBREV_TO_FULL and "VEN" in TEAM_ABBREV_TO_FULL
    assert "CRE" not in TEAM_ABBREV_TO_FULL and "PIS" not in TEAM_ABBREV_TO_FULL and "VER" not in TEAM_ABBREV_TO_FULL


def test_promoted_teams_are_the_promoted_sides():
    assert PROMOTED_TEAMS == PROMOTED | {"VEN", "FRO", "MON"}
    assert PROMOTED_TEAM_CODES == {"ven", "fro", "mon"}


def test_is_current_serie_a_team_follows_verified_roster():
    for team in CURRENT_SERIE_A:
        assert is_current_serie_a_team(team), f"{team} must be current Serie A"
    for team in NOT_IN_SERIE_A:
        assert not is_current_serie_a_team(team), f"{team} must NOT be current Serie A"


def test_pianetafanta_scrapes_the_verified_roster():
    assert len(TEAMS) == 20
    assert {"FROSINONE", "MONZA", "VENEZIA"} <= set(TEAMS)
    assert not {"CREMONESE", "PISA", "VERONA"} & set(TEAMS)


def test_schema_teams_table_matches_verified_roster(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    rows = {
        r[0]
        for r in conn.execute("SELECT code FROM teams WHERE season = '2026/27'")
    }
    conn.close()
    assert rows == {"ata", "bol", "cag", "com", "fio", "fro", "gen", "int",
                    "juv", "laz", "lec", "mil", "mon", "nap", "par", "rom",
                    "sas", "tor", "udi", "ven"}
    assert not {"cre", "pis", "ver"} & rows