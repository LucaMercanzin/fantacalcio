from ranking.auction_intelligence import (
    compute_all_opponent_models,
    compute_auction_timing,
    compute_dynamic_max_bid,
    compute_expected_auction_price,
    compute_max_theoretical_bid,
    compute_opponent_budget_model,
    compute_price_distribution,
    compute_price_inflation,
    compute_scarcity_tier,
)


def test_compute_price_inflation_detects_overpaying():
    purchases = [
        {"price_paid": 35, "fair_price": 30},
        {"price_paid": 40, "fair_price": 32},
        {"price_paid": 20, "fair_price": 18},
    ]
    result = compute_price_inflation(purchases)
    assert result["inflation_pct"] > 0
    assert result["sample_size"] == 3


def test_compute_price_inflation_none_below_min_sample():
    result = compute_price_inflation([{"price_paid": 35, "fair_price": 30}])
    assert result["inflation_pct"] is None


def test_compute_expected_auction_price_scales_with_inflation():
    baseline = compute_expected_auction_price(30, None)
    inflated = compute_expected_auction_price(30, 20.0)
    assert inflated > baseline == 30


def test_compute_scarcity_tier_labels():
    assert compute_scarcity_tier(0)["label"] == "Critica"
    assert compute_scarcity_tier(2)["label"] == "Alta"
    assert compute_scarcity_tier(10)["label"] == "Bassa"


def test_compute_max_theoretical_bid_reserves_one_credit_per_remaining_slot():
    # budget 100, 5 slots left (including this one): reserve 4 credits for the rest
    assert compute_max_theoretical_bid(100, 5) == 96
    assert compute_max_theoretical_bid(100, 0) == 0.0


def test_compute_dynamic_max_bid_never_exceeds_theoretical_cap():
    result = compute_dynamic_max_bid(
        fair_price=30, budget_remaining=40, slots_remaining=3,
        inflation_pct=50, alternatives_remaining=0,
    )
    assert result["max_bid"] <= result["theoretical_budget_cap"]
    assert result["max_bid"] >= 30


def test_compute_dynamic_max_bid_rises_with_inflation_and_scarcity():
    calm = compute_dynamic_max_bid(30, 300, 10, inflation_pct=0, alternatives_remaining=10)
    hot = compute_dynamic_max_bid(30, 300, 10, inflation_pct=30, alternatives_remaining=0)
    assert hot["max_bid"] > calm["max_bid"]


def test_compute_price_distribution_none_below_min_sample():
    assert compute_price_distribution(30, [1.1, 1.2]) is None


def test_compute_price_distribution_orders_percentiles():
    ratios = [0.9, 1.0, 1.05, 1.1, 1.2, 1.3]
    dist = compute_price_distribution(30, ratios)
    assert dist["p25"] <= dist["median"] <= dist["p75"] <= dist["p90"]


def test_compute_opponent_budget_model_tracks_spend_and_slots():
    picks = [
        {"price_paid": 40, "role_classic": "A"},
        {"price_paid": 20, "role_classic": "D"},
    ]
    model = compute_opponent_budget_model("Avversario 1", picks, total_credits=500)
    assert model["spent"] == 60
    assert model["players_bought"] == 2
    assert model["budget_remaining"] == 440
    assert model["roles_missing"]["A"] == 5  # 6 slot totali - 1 preso


def test_compute_all_opponent_models_ranks_by_threat():
    picks = [
        {"opponent_name": "Ricco", "player_id": 1, "price_paid": 5, "role_classic": "D"},
        {"opponent_name": "Squattrinato", "player_id": 2, "price_paid": 240, "role_classic": "A"},
        {"opponent_name": "Squattrinato", "player_id": 3, "price_paid": 240, "role_classic": "A"},
    ]
    models = compute_all_opponent_models(picks, total_credits=500)
    names = [m["opponent_name"] for m in models]
    assert "Ricco" in names and "Squattrinato" in names
    # Ricco has spent almost nothing and bids low: far less threatening than
    # someone who has already blown most of the budget on big-ticket buys.
    assert models[0]["opponent_name"] == "Ricco"
    assert all(0 <= m["threat_score"] <= 100 for m in models)


def test_compute_auction_timing_pass_when_role_full():
    result = compute_auction_timing(0, compute_scarcity_tier(5), 0, 100, 30)
    assert result["action"] == "pass"


def test_compute_auction_timing_buy_now_when_scarce():
    result = compute_auction_timing(2, compute_scarcity_tier(1), 5, 100, 30)
    assert result["action"] == "buy_now"


def test_compute_auction_timing_save_budget_when_low_on_credits():
    result = compute_auction_timing(2, compute_scarcity_tier(10), 0, 10, 30)
    assert result["action"] == "save_budget"
