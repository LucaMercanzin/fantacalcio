from scrapers.pianetafanta import parse_team_rows

PARMA_ROWS = [
    ["C", "C", "BERNABÈ A.PARMAP 0%T 0%", "29,2", "29,2", "(+0)"],
    ["A", "A", "ELPHEGE N.PARMAP 0%T 0%", "22,1", "22,1", "(+0)"],
]


def test_parse_team_rows_extracts_players():
    records = parse_team_rows(PARMA_ROWS, "PARMA")

    assert len(records) == 2
    bernabe = records[0]
    assert bernabe.name == "BERNABÈ A."
    assert bernabe.team == "PARMA"
    assert bernabe.role_classic == "C"
    assert bernabe.role_mantra == "C"
    assert bernabe.price_current == 29.2
    assert bernabe.price_initial == 29.2
    assert bernabe.source == "pianetafanta"


def test_parse_team_rows_skips_incomplete_rows():
    assert parse_team_rows([["C", "C"]], "PARMA") == []
