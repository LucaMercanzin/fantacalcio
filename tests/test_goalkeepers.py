from ranking.goalkeepers import build_goalkeeper_depth_chart


def _row(player_id, team, score, is_promoted=False):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "team": team, "score": score, "is_promoted": is_promoted,
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
