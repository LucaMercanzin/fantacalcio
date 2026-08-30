import random

from matching.player_matcher import (
    match_name_to_player,
    match_name_to_player_any_team,
    match_records,
    match_records_with_confidence,
    normalize_name,
    normalize_team,
)
from scrapers.base import PlayerRecord


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


# TASK-009 --------------------------------------------------------------

def test_normalize_team_resolves_a_club_name_variant_via_alias_map():
    alias_map = {"hellasverona": "ver"}

    assert normalize_team("Hellas Verona", alias_map) == normalize_team("Verona", alias_map)


def test_normalize_team_falls_back_to_truncation_without_an_alias():
    assert normalize_team("Hellas Verona") != normalize_team("Verona")


def test_match_name_to_player_refuses_ambiguous_teammates_sharing_a_surname():
    """Two real teammates who share a surname (Lautaro Martinez and Josep
    Martinez, both Inter) — a bare "Martinez" should not silently resolve to
    either one via _initials_conflict (point 2), which match_name_to_player
    didn't apply before TASK-009."""
    players = [
        {"id": 1, "canonical_name": "Lautaro Martinez", "team": "Inter"},
        {"id": 2, "canonical_name": "Josep Martinez", "team": "Inter"},
    ]

    assert match_name_to_player("Martinez", "Inter", players) is None


def test_match_name_to_player_any_team_refuses_ambiguous_teammates_sharing_a_surname():
    players = [
        {"id": 1, "canonical_name": "Lautaro Martinez", "team": "Inter"},
        {"id": 2, "canonical_name": "Josep Martinez", "team": "Inter"},
    ]

    assert match_name_to_player_any_team("Martinez", players, threshold=50) is None


def test_match_name_to_player_refuses_an_exact_tie_even_above_near_exact_score():
    """Point 3: a tie for best score is ambiguous even when both candidates
    are a near-exact match (>=NEAR_EXACT_SCORE) — there's no signal left to
    prefer one over the other."""
    players = [
        {"id": 1, "canonical_name": "Marco Bianchi", "team": "Roma"},
        {"id": 2, "canonical_name": "Marco Bianchi", "team": "Roma"},
    ]

    assert match_name_to_player("Marco Bianchi", "Roma", players) is None


def test_match_records_grouping_is_invariant_to_input_order():
    records = [
        _record("Lautaro Martinez", "Inter", "fantacalcio_it"),
        _record("Martinez L.", "Inter", "gazzetta"),
        _record("Yann Sommer", "Inter", "fantacalcio_it"),
        _record("Marco Rossi", "Roma", "gazzetta"),
    ]

    baseline = match_records(records)
    baseline_keys = sorted(baseline.keys())
    baseline_group_sources = sorted(
        tuple(sorted(r.source for r in group)) for group in baseline.values()
    )

    shuffled = list(records)
    rng = random.Random(42)
    for _ in range(5):
        rng.shuffle(shuffled)
        result = match_records(shuffled)
        assert sorted(result.keys()) == baseline_keys
        assert sorted(
            tuple(sorted(r.source for r in group)) for group in result.values()
        ) == baseline_group_sources
