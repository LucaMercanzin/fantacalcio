from ranking.role_comparison import compute_role_comparison


def _row(player_id, fantamedia, score, goals, assists, appearances):
    return {
        "player_id": player_id, "fantamedia": fantamedia, "score": score,
        "season_goals_scored": goals, "season_assists": assists,
        "appearances": appearances,
    }


def test_computes_percentile_and_role_average_for_each_metric():
    rows = [
        _row(1, 8.0, 90.0, 20, 5, 35),
        _row(2, 6.0, 50.0, 5, 2, 25),
        _row(3, 6.5, 55.0, 8, 3, 30),
    ]

    comparison = compute_role_comparison(rows, player_id=1)

    assert comparison["fantamedia"]["player"] == 8.0
    assert comparison["fantamedia"]["role_avg"] == round((8.0 + 6.0 + 6.5) / 3, 1)
    # bisect_left(sorted_values, own_value) excludes the player's own slot
    # from the count-below (same convention as ranking.tiers._percentile_rank,
    # which this mirrors) — the single best of 3 lands at 2/3*100, not 100.0.
    assert comparison["fantamedia"]["percentile"] == 66.7
    assert comparison["fantamedia"]["label"] == "Fantamedia"


def test_returns_empty_dict_when_player_not_in_role_rows():
    rows = [_row(2, 6.0, 50.0, 5, 2, 25)]

    assert compute_role_comparison(rows, player_id=999) == {}


def test_skips_metric_when_players_own_value_is_none():
    rows = [
        {"player_id": 1, "fantamedia": None, "score": 90.0, "appearances": 35,
         "season_goals_scored": None, "season_assists": None},
        {"player_id": 2, "fantamedia": 6.0, "score": 50.0, "appearances": 25,
         "season_goals_scored": 5, "season_assists": 2},
    ]

    comparison = compute_role_comparison(rows, player_id=1)

    assert "fantamedia" not in comparison
    assert "score" in comparison
