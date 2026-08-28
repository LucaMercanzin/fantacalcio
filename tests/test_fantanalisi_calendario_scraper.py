from scrapers.fantanalisi_calendario import parse_team_scores

SAMPLE_ROWS = [
    {"team": "Venezia", "score": "65"},
    {"team": "Juventus", "score": "62"},
]


def test_parse_team_scores_extracts_team_and_score():
    records = parse_team_scores(SAMPLE_ROWS)

    assert records == [
        {"team": "Venezia", "score": 65},
        {"team": "Juventus", "score": 62},
    ]


def test_parse_team_scores_skips_rows_without_team_name():
    records = parse_team_scores([{"team": "", "score": "50"}])

    assert records == []


def test_parse_team_scores_handles_non_numeric_score():
    records = parse_team_scores([{"team": "Venezia", "score": "-"}])

    assert records == [{"team": "Venezia", "score": None}]
