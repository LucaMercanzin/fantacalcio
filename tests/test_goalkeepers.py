from ranking.goalkeepers import build_goalkeeper_depth_chart


def _row(player_id, team, score, is_promoted=False, appearances=None):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "team": team, "score": score, "is_promoted": is_promoted,
        "appearances": appearances,
    }


def test_groups_by_team_starter_and_backup():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Inter", 65.0),
        _row(4, "Inter", 60.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 1
    assert napoli["backup"]["player_id"] == 2
    assert chart["warnings"] == []


def test_third_choice_keeper_excluded_from_depth_chart():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Napoli", 30.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    ids = {napoli["starter"]["player_id"], napoli["backup"]["player_id"]}
    assert ids == {1, 2}


def test_warns_when_team_has_only_one_identifiable_keeper():
    rows = [_row(1, "Como", 55.0)]

    chart = build_goalkeeper_depth_chart(rows)

    como = next(t for t in chart["teams"] if t["team"] == "Como")
    assert como["starter"]["player_id"] == 1
    assert como["backup"] is None
    assert chart["warnings"] == ["Como"]


def test_expected_team_with_no_identifiable_keeper_gets_a_warning_not_silence():
    rows = [_row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0)]

    chart = build_goalkeeper_depth_chart(
        rows, expected_teams={"Napoli": False, "Lazio": False},
    )

    lazio = next(t for t in chart["teams"] if t["team"] == "Lazio")
    assert lazio["starter"] is None
    assert lazio["backup"] is None
    assert chart["missing"] == ["Lazio"]
    assert chart["warnings"] == []


def test_promoted_teams_sorted_last():
    rows = [
        _row(1, "Venezia", 60.0, is_promoted=True),
        _row(2, "Venezia", 50.0, is_promoted=True),
        _row(3, "Atalanta", 60.0),
        _row(4, "Atalanta", 50.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    team_order = [t["team"] for t in chart["teams"]]
    assert team_order == ["Atalanta", "Venezia"]


def test_appearances_outrank_score_for_starter_selection():
    """TASK-004b / P1-021: portieri.md §8 forbids ranking by rating; a keeper
    with fewer appearances must not beat one with more, even with a higher
    score (e.g. a backup with no fantamedia scored on avg_rating alone)."""
    rows = [
        _row(1, "Como", 66.5, appearances=None),  # no real fantamedia (P0-002)
        _row(2, "Como", 60.7, appearances=37),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    como = next(t for t in chart["teams"] if t["team"] == "Como")
    assert como["starter"]["player_id"] == 2
    assert como["backup"]["player_id"] == 1


def test_score_is_only_a_tie_break_when_appearances_are_equal():
    rows = [
        _row(1, "Napoli", 50.0, appearances=30),
        _row(2, "Napoli", 70.0, appearances=30),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 2


def test_anti_error_counts_exposed_per_portieri_md_section_13():
    rows = [
        _row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0),
        _row(3, "Como", 55.0),
    ]

    chart = build_goalkeeper_depth_chart(
        rows, expected_teams={"Napoli": False, "Como": False, "Lazio": False},
    )

    assert chart["n_teams"] == 3
    assert chart["n_goalkeepers"] == 3
    assert chart["duplicates"] == []


def test_anti_error_flags_duplicate_player_across_slots():
    rows = [
        _row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0),
        _row(1, "Inter", 65.0),  # same player_id matched under two teams
    ]

    chart = build_goalkeeper_depth_chart(rows)

    assert chart["duplicates"] == [1]
