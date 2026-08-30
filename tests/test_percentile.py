from ranking.percentile import percentile_rank


def test_best_value_lands_at_exactly_100():
    values = sorted([10, 25, 6.5, 40, 18])
    assert percentile_rank(max(values), values) == 100.0


def test_worst_value_lands_at_exactly_0():
    values = sorted([10, 25, 6.5, 40, 18])
    assert percentile_rank(min(values), values) == 0.0


def test_tied_values_share_the_averaged_rank():
    values = sorted([5, 5, 10])
    assert percentile_rank(5, values) == 25.0
    assert percentile_rank(10, values) == 100.0


def test_single_player_population_is_the_best_by_definition():
    assert percentile_rank(42, [42]) == 100.0


def test_empty_population_falls_back_to_neutral():
    assert percentile_rank(42, []) == 50.0
