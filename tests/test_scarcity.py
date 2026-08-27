from ranking.scarcity import compute_scarcity


def _row(pid, decision_score):
    return {"player_id": pid, "decision_score": decision_score}


def test_no_comparable_alternatives_is_maximum_scarcity():
    player = _row(1, 80.0)
    available = [player, _row(2, 30.0), _row(3, 10.0)]
    assert compute_scarcity(player, available) == 100.0


def test_more_comparable_alternatives_lowers_scarcity():
    player = _row(1, 80.0)
    few_alternatives = [player, _row(2, 75.0)]
    many_alternatives = [player] + [_row(i, 75.0) for i in range(2, 10)]
    assert compute_scarcity(player, many_alternatives) < compute_scarcity(player, few_alternatives)


def test_alternative_below_comparable_ratio_does_not_reduce_scarcity():
    player = _row(1, 100.0)
    # 50 is well under 90% of 100, shouldn't count as comparable
    available = [player, _row(2, 50.0)]
    assert compute_scarcity(player, available) == 100.0
