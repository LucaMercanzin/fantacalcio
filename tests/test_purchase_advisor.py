from ranking.purchase_advisor import compute_marginal_squad_value, evaluate_purchase


def _player(score=60.0, price_current=20, value_for_money=None, rank_in_role=None):
    return {
        "score": score, "price_current": price_current, "role_classic": "A",
        "value_for_money": value_for_money, "rank_in_role": rank_in_role,
    }


def test_role_already_full_is_useless_regardless_of_price():
    slot = {"filled": 6, "total": 6, "remaining": 0}
    result = evaluate_purchase(_player(), price=1, slot=slot, roster_role_scores=[50.0])
    assert result["verdict"] == "ruolo_pieno"


def test_useless_even_cheap_when_already_own_better_players():
    slot = {"filled": 5, "total": 6, "remaining": 1}
    player = _player(score=40.0)
    result = evaluate_purchase(player, price=1, slot=slot, roster_role_scores=[70.0, 65.0])
    assert result["verdict"] == "inutile_hai_di_meglio"


def test_too_expensive_when_price_far_above_listed_value_for_money():
    slot = {"filled": 3, "total": 6, "remaining": 3}
    player = _player(score=60.0, price_current=20, value_for_money=30.0)
    # paying 10x the listed price tanks the value-for-money ratio
    result = evaluate_purchase(player, price=200, slot=slot, roster_role_scores=[])
    assert result["verdict"] == "troppo_caro"


def test_bargain_when_price_is_well_below_listed_price():
    slot = {"filled": 3, "total": 6, "remaining": 3}
    player = _player(score=60.0, price_current=20, value_for_money=30.0)
    result = evaluate_purchase(player, price=5, slot=slot, roster_role_scores=[])
    assert result["verdict"] == "affare"


def test_all_in_recommended_on_last_slot_with_a_top_ranked_player():
    slot = {"filled": 5, "total": 6, "remaining": 1}
    player = _player(score=60.0, price_current=20, value_for_money=30.0, rank_in_role=2)
    result = evaluate_purchase(player, price=200, slot=slot, roster_role_scores=[])
    assert result["verdict"] == "troppo_caro"
    assert result["all_in_recommended"] is True


def test_marginal_value_is_full_score_when_slot_open():
    slot = {"filled": 2, "total": 6, "remaining": 4}
    assert compute_marginal_squad_value(_player(score=60.0), slot, [70.0]) == 60.0


def test_marginal_value_is_gap_over_weakest_owned_when_slot_full():
    slot = {"filled": 6, "total": 6, "remaining": 0}
    assert compute_marginal_squad_value(_player(score=60.0), slot, [50.0, 55.0]) == 10.0


def test_marginal_value_floors_at_zero_when_not_an_upgrade():
    slot = {"filled": 6, "total": 6, "remaining": 0}
    assert compute_marginal_squad_value(_player(score=40.0), slot, [50.0, 55.0]) == 0.0
