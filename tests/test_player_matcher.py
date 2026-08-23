from scrapers.base import PlayerRecord
from matching.player_matcher import match_records, normalize_name


def _record(name, team, source):
    return PlayerRecord(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=10, price_initial=10, status="ok", fantamedia=6,
        avg_rating=6, appearances=10, photo_url=None, source=source,
    )


def test_normalize_name_strips_case_and_punctuation():
    assert normalize_name("Lautaro Martinez") == normalize_name("lautaro   martinez")


def test_match_records_groups_same_player_across_sources():
    records = [
        _record("Lautaro Martinez", "Inter", "fantacalcio_it"),
        _record("Lautaro", "Inter", "gazzetta"),
        _record("Yann Sommer", "Inter", "fantacalcio_it"),
    ]

    groups = match_records(records)

    assert len(groups) == 2
    lautaro_group = next(v for k, v in groups.items() if "Lautaro" in k[0])
    assert len(lautaro_group) == 2
    assert {r.source for r in lautaro_group} == {"fantacalcio_it", "gazzetta"}


def test_match_records_keeps_different_teams_separate():
    records = [
        _record("Marco Rossi", "Milan", "fantacalcio_it"),
        _record("Marco Rossi", "Roma", "gazzetta"),
    ]

    groups = match_records(records)

    assert len(groups) == 2


def test_match_records_matches_team_abbreviation_to_full_name():
    records = [
        _record("Martinez L.", "INT", "fantacalcio_it"),
        _record("Martinez Lautaro", "Inter", "fantacalciopedia"),
    ]

    groups = match_records(records)

    assert len(groups) == 1
    group = next(iter(groups.values()))
    assert {r.source for r in group} == {"fantacalcio_it", "fantacalciopedia"}
