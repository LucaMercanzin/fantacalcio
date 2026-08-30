from ranking.price_engine import compute_value_index


def test_value_index_none_without_inputs():
    assert compute_value_index(None, 15.0) is None
    assert compute_value_index(1.5, None) is None
    assert compute_value_index(1.5, 0) is None


def test_value_index_100_at_exactly_the_role_median():
    assert compute_value_index(15.0, 15.0) == 100


def test_value_index_above_100_when_more_efficient_than_median():
    assert compute_value_index(19.5, 15.0) == 130


def test_value_index_below_100_when_less_efficient_than_median():
    assert compute_value_index(7.5, 15.0) == 50
