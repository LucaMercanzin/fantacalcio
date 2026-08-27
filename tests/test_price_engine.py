from ranking.price_engine import (
    compute_fair_price, compute_max_price, compute_price_recommendation, BUY, PASS, BORDERLINE,
)


def test_fair_price_none_without_median_vfm():
    assert compute_fair_price(60.0, None) is None
    assert compute_fair_price(60.0, 0) is None


def test_fair_price_matches_role_median_value_for_money():
    # median VFM 15 -> a player scoring 60 is "fair" at a price where his own
    # VFM (score/price*10) also equals 15, i.e. price = 60/15*10 = 40
    assert compute_fair_price(60.0, 15.0) == 40.0


def test_max_price_increases_with_scarcity_and_replacement_advantage():
    base = compute_max_price(fair_price=40.0, scarcity=0, replacement_advantage=0)
    scarce = compute_max_price(fair_price=40.0, scarcity=100, replacement_advantage=0)
    irreplaceable = compute_max_price(fair_price=40.0, scarcity=0, replacement_advantage=20)
    assert base == 40.0
    assert scarce > base
    assert irreplaceable > base


def test_recommendation_status_buy_when_price_within_max():
    result = compute_price_recommendation(
        score=60.0, price_current=35, median_value_for_money=15.0,
        scarcity=0, replacement_advantage=0,
    )
    assert result["fair_price"] == 40.0
    assert result["status"] == BUY


def test_recommendation_status_pass_when_price_well_above_max():
    result = compute_price_recommendation(
        score=60.0, price_current=60, median_value_for_money=15.0,
        scarcity=0, replacement_advantage=0,
    )
    assert result["status"] == PASS


def test_recommendation_status_borderline_just_above_max():
    # max_price = 40 with no scarcity/replacement premium; 41 is only ~2.5% over
    result = compute_price_recommendation(
        score=60.0, price_current=41, median_value_for_money=15.0,
        scarcity=0, replacement_advantage=0,
    )
    assert result["status"] == BORDERLINE


def test_recommendation_status_none_without_market_price():
    result = compute_price_recommendation(
        score=60.0, price_current=None, median_value_for_money=15.0,
        scarcity=0, replacement_advantage=0,
    )
    assert result["status"] is None
