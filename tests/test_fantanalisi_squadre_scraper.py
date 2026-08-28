from db import repository
from db.connection import get_connection, init_db
from scrapers.fantanalisi_squadre import parse_sections, save_team_strength

ATALANTA_SECTION = {"team": "Atalanta", "stats": ["1.81", "1.36", "10.6"]}
# Squadra neopromossa: la sezione esiste ma senza il blocco xG/xGA/PPDA
# (nessuno storico Understat di Serie A).
FROSINONE_SECTION = {"team": "Frosinone", "stats": []}


def test_parse_sections_extracts_xg_xga_ppda():
    records = parse_sections([ATALANTA_SECTION])

    assert len(records) == 1
    assert records[0] == {"team": "Atalanta", "xg": 1.81, "xga": 1.36, "ppda": 10.6}


def test_parse_sections_none_for_team_without_understat_history():
    records = parse_sections([FROSINONE_SECTION])

    assert records[0] == {"team": "Frosinone", "xg": None, "xga": None, "ppda": None}


def test_parse_sections_skips_sections_without_team_name():
    assert parse_sections([{"team": "", "stats": ["1.0", "1.0", "10.0"]}]) == []


def test_parse_sections_handles_comma_decimal_separator():
    section = {"team": "Bologna", "stats": ["1,32", "1,34", "9,8"]}
    records = parse_sections([section])

    assert records[0]["xg"] == 1.32


def test_save_team_strength_persists_and_is_queryable(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    records = parse_sections([ATALANTA_SECTION, FROSINONE_SECTION])
    saved = save_team_strength(conn, records, scrape_date="2026-08-27")

    assert saved == 2
    latest = repository.get_all_latest_team_strength(conn)
    assert latest["Atalanta"]["xg"] == 1.81
    assert latest["Frosinone"]["xg"] is None
    conn.close()


def test_save_team_strength_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    save_team_strength(conn, [{"team": "Atalanta", "xg": 1.5, "xga": 1.4, "ppda": 11.0}],
                        scrape_date="2026-08-20")
    save_team_strength(conn, [{"team": "Atalanta", "xg": 1.81, "xga": 1.36, "ppda": 10.6}],
                        scrape_date="2026-08-27")

    rows = conn.execute("SELECT * FROM team_strength WHERE team = 'Atalanta'").fetchall()
    assert len(rows) == 2

    latest = repository.get_all_latest_team_strength(conn)
    assert latest["Atalanta"]["xg"] == 1.81
    assert latest["Atalanta"]["scrape_date"] == "2026-08-27"
    conn.close()
