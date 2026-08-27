from ranking.correlation import find_correlations


def _row(player_id, name, team, role_classic, role_mantra=None, goals=0, assists=0):
    return {
        "player_id": player_id, "canonical_name": name, "team": team,
        "role_classic": role_classic, "role_mantra": role_mantra,
        "season_goals_scored": goals, "season_assists": assists,
    }


def test_flags_positive_correlation_assistman_and_goleador_same_team():
    rows = [
        _row(1, "Assistman", "Inter", "C", "E", goals=1, assists=6),
        _row(2, "Goleador", "Inter", "A", "PC", goals=10, assists=0),
    ]

    result = find_correlations(rows)

    assert len(result["positive"]) == 1
    pair = result["positive"][0]
    assert pair["player_a"]["player_id"] == 1
    assert pair["player_b"]["player_id"] == 2


def test_no_positive_correlation_across_different_teams():
    rows = [
        _row(1, "Assistman", "Inter", "C", "E", goals=1, assists=6),
        _row(2, "Goleador", "Milan", "A", "PC", goals=10, assists=0),
    ]

    result = find_correlations(rows)

    assert result["positive"] == []


def test_flags_negative_correlation_same_contested_role_same_team():
    rows = [
        _row(1, "Punta A", "Napoli", "A", "PC", goals=8, assists=1),
        _row(2, "Punta B", "Napoli", "A", "PC", goals=5, assists=0),
    ]

    result = find_correlations(rows)

    assert len(result["negative"]) == 1
    ids = {result["negative"][0]["player_a"]["player_id"],
           result["negative"][0]["player_b"]["player_id"]}
    assert ids == {1, 2}


def test_no_negative_correlation_for_non_contested_role_mantra():
    rows = [
        _row(1, "Centrale A", "Napoli", "D", "DC"),
        _row(2, "Centrale B", "Napoli", "D", "DC"),
    ]

    result = find_correlations(rows)

    assert result["negative"] == []


def test_ignores_portieri():
    rows = [
        _row(1, "Titolare", "Roma", "P", "POR"),
        _row(2, "Riserva", "Roma", "P", "POR"),
    ]

    result = find_correlations(rows)

    assert result["positive"] == []
    assert result["negative"] == []
