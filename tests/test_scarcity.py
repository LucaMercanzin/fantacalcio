from ranking.scarcity import compute_scarcity


def _row(pid, score, price=10):
    return {"player_id": pid, "score": score, "price_current": price}


def test_no_comparable_alternatives_is_maximum_scarcity():
    player = _row(1, 80.0)
    available = [player, _row(2, 30.0), _row(3, 10.0)]
    assert compute_scarcity(player, available, slots_remaining=4) == 100.0


def test_more_comparable_alternatives_lowers_scarcity():
    player = _row(1, 80.0)
    few_alternatives = [player, _row(2, 78.0)]
    many_alternatives = [player] + [_row(i, 78.0) for i in range(2, 10)]
    assert (
        compute_scarcity(player, many_alternatives, slots_remaining=4)
        < compute_scarcity(player, few_alternatives, slots_remaining=4)
    )


def test_alternative_outside_score_gap_does_not_count_as_comparable():
    player = _row(1, 100.0)
    # 50 is far outside COMPARABLE_SCORE_GAP (an absolute difference, not a
    # ratio — decision_score/score have no meaningful zero to take a % of).
    available = [player, _row(2, 50.0)]
    assert compute_scarcity(player, available, slots_remaining=4) == 100.0


def test_decay_tuned_to_role_size_not_a_fixed_constant():
    """P1-009: a fixed DECAY_SCALE=4 made scarcity ~0 for anyone outside the
    top handful of a 150-candidate role. Tying the decay to slots_remaining
    keeps the score meaningful regardless of how many total candidates exist
    in the role, as long as the *comparable* pool is realistic."""
    player = _row(1, 80.0)
    # A large role (150 candidates) with only 2 genuinely comparable
    # (within COMPARABLE_SCORE_GAP) alternatives.
    available = (
        [player, _row(2, 79.0), _row(3, 78.0)]
        + [_row(i, 78.0 - i) for i in range(4, 150)]  # all far outside the gap
    )
    scarcity = compute_scarcity(player, available, slots_remaining=8)
    assert scarcity > 50.0  # not the ~0 the old fixed-scale formula gave


def test_unaffordable_alternatives_are_excluded_when_spendable_given():
    player = _row(1, 80.0, price=20)
    expensive_alternative = _row(2, 79.0, price=100)
    affordable_alternative = _row(3, 78.0, price=15)

    with_only_expensive = compute_scarcity(
        player, [player, expensive_alternative], slots_remaining=4, spendable=50,
    )
    with_affordable_too = compute_scarcity(
        player, [player, expensive_alternative, affordable_alternative],
        slots_remaining=4, spendable=50,
    )

    # The unaffordable one shouldn't count: same result as if it weren't there.
    assert with_only_expensive == 100.0
    assert with_affordable_too < with_only_expensive


def test_no_spendable_filter_when_not_given():
    player = _row(1, 80.0, price=20)
    expensive_alternative = _row(2, 79.0, price=1000)

    assert compute_scarcity(player, [player, expensive_alternative], slots_remaining=4) < 100.0


def test_none_score_is_zero_scarcity_not_a_crash():
    # insufficient_data players (P0-002) have score=None.
    player = {"player_id": 1, "score": None, "price_current": 10}
    assert compute_scarcity(player, [player], slots_remaining=4) == 0.0
