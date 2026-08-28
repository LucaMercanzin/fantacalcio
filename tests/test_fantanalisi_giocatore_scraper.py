from scrapers.fantanalisi_giocatore import parse_percentile_titles

SAMPLE_TITLES = [
    "Kolo Muani — xG/90: 53° percentile",
    "Kolo Muani — xA/90: 43° percentile",
    "Kolo Muani — Tiri/90: 22° percentile",
    "Kolo Muani — Rifin.: 63° percentile",
    "Kolo Muani — Coinv.: 34° percentile",
    "Kolo Muani — Minuti: 43° percentile",
]


def test_parse_percentile_titles_extracts_all_metrics():
    result = parse_percentile_titles(SAMPLE_TITLES)

    assert result == {
        "xg90_percentile": 53, "xa90_percentile": 43, "shots90_percentile": 22,
        "key_passes90_percentile": 63, "involvement_percentile": 34,
        "minutes_percentile": 43,
    }


def test_parse_percentile_titles_ignores_unrelated_titles():
    result = parse_percentile_titles(["Some unrelated tooltip text"])

    assert result == {
        "xg90_percentile": None, "xa90_percentile": None, "shots90_percentile": None,
        "key_passes90_percentile": None, "involvement_percentile": None,
        "minutes_percentile": None,
    }


def test_parse_percentile_titles_handles_empty_list():
    result = parse_percentile_titles([])

    assert all(v is None for v in result.values())
