from ranking.replacement import compute_replacement_advantage, compute_replacement_level


def _row(pid, score):
    return {"player_id": pid, "score": score}


def test_replacement_level_is_best_score_among_others():
    player = _row(1, 90.0)
    available = [player, _row(2, 70.0), _row(3, 55.0)]
    assert compute_replacement_level(player, available) == 70.0


def test_replacement_level_zero_when_no_alternatives():
    player = _row(1, 90.0)
    assert compute_replacement_level(player, [player]) == 0.0


def test_replacement_advantage_is_difference_from_best_alternative():
    player = _row(1, 90.0)
    available = [player, _row(2, 70.0)]
    assert compute_replacement_advantage(player, available) == 20.0
