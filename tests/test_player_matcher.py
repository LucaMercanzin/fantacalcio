from scrapers.base import PlayerRecord
from matching.player_matcher import (
    match_records, match_records_with_confidence, match_name_to_player,
    match_name_to_player_any_team, normalize_name,
)


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


def test_match_records_with_confidence_gives_full_confidence_to_group_anchor():
    records = [_record("Lautaro Martinez", "Inter", "fantacalcio_it")]

    groups = match_records_with_confidence(records)

    (record, confidence), = next(iter(groups.values()))
    assert record.source == "fantacalcio_it"
    assert confidence == 100.0


def test_match_records_with_confidence_scores_fuzzy_match_below_full():
    records = [
        _record("Lautaro Martinez", "Inter", "fantacalcio_it"),
        _record("Martinez L.", "Inter", "gazzetta"),
    ]

    groups = match_records_with_confidence(records)
    group = next(iter(groups.values()))

    confidences = {record.source: confidence for record, confidence in group}
    assert confidences["fantacalcio_it"] == 100.0
    assert confidences["gazzetta"] < 100.0
    assert confidences["gazzetta"] >= 85.0


def test_match_name_to_player_finds_best_team_and_name_match():
    players = [
        {"id": 1, "canonical_name": "Lautaro Martinez", "team": "Inter"},
        {"id": 2, "canonical_name": "Marco Rossi", "team": "Roma"},
    ]

    found = match_name_to_player("Lautaro", "Inter", players)

    assert found["id"] == 1


def test_match_name_to_player_returns_none_below_threshold():
    players = [{"id": 1, "canonical_name": "Marco Rossi", "team": "Roma"}]

    assert match_name_to_player("Completely Different", "Roma", players) is None


def test_match_name_to_player_any_team_finds_transferred_player():
    players = [{"id": 1, "canonical_name": "Lautaro Martinez", "team": "Inter"}]

    # Player's team in a past season's record no longer matches his current team
    found = match_name_to_player_any_team("Lautaro Martinez", players)

    assert found["id"] == 1


def test_match_name_to_player_any_team_respects_custom_threshold():
    players = [{"id": 1, "canonical_name": "Lautaro Martinez", "team": "Inter"}]

    # A middling match should pass a lenient threshold but not a strict one.
    assert match_name_to_player_any_team("Lautaro Martinz", players, threshold=70) is not None
    assert match_name_to_player_any_team("Something Else Entirely", players, threshold=92) is None
