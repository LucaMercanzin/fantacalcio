from ranking.lp_optimizer import ROLE_SLOTS, build_optimal_squad


def _player(pid, role, score, price):
    return {
        "player_id": pid, "canonical_name": f"Player {pid}", "role_classic": role,
        "score": score, "price_current": price,
    }


def test_from_scratch_fills_all_role_slots_within_budget():
    players_by_role = {
        "P": [_player(1, "P", 60, 10), _player(2, "P", 50, 5), _player(3, "P", 40, 3),
              _player(4, "P", 30, 1)],
        "D": [_player(10 + i, "D", 50 - i, 5) for i in range(10)],
        "C": [_player(30 + i, "C", 50 - i, 5) for i in range(10)],
        "A": [_player(50 + i, "A", 50 - i, 5) for i in range(8)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_player_ids=set(), taken_ids=set(),
        mode="from_scratch",
    )

    assert result["status"] == "optimal"
    total_selected = sum(len(players) for players in result["squad"].values())
    assert total_selected == sum(ROLE_SLOTS.values())
    for role, needed in ROLE_SLOTS.items():
        assert len(result["squad"][role]) == needed
    assert result["total_cost"] <= 500


def test_from_scratch_prefers_higher_score_within_budget():
    players_by_role = {
        "P": [_player(1, "P", 100, 500), _player(2, "P", 10, 1),
              _player(3, "P", 10, 1), _player(4, "P", 10, 1)],
        "D": [_player(10 + i, "D", 10, 1) for i in range(8)],
        "C": [_player(30 + i, "C", 10, 1) for i in range(8)],
        "A": [_player(50 + i, "A", 10, 1) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=25, roster_player_ids=set(), taken_ids=set(),
        mode="from_scratch",
    )

    # player 1 costs the entire budget alone -- can't be afforded alongside
    # the other 24 mandatory slots, so a cheaper goalkeeper must be picked
    # even though it scores lower.
    assert result["status"] == "optimal"
    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert 1 not in p_ids


def test_constrained_mode_keeps_roster_fixed_and_fills_remaining_slots():
    players_by_role = {
        "P": [_player(1, "P", 60, 10), _player(2, "P", 40, 5), _player(3, "P", 30, 5)],
        "D": [_player(10 + i, "D", 50 - i, 5) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 5) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 5) for i in range(6)],
    }
    # player 1 (P) already owned, paid 20 credits
    result = build_optimal_squad(
        players_by_role, budget=500 - 20, roster_player_ids={1}, taken_ids=set(),
        mode="constrained", roster_prices={1: 20},
    )

    assert result["status"] == "optimal"
    assert len(result["squad"]["P"]) == 3
    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert 1 in p_ids  # roster player stays fixed
    # the roster player's paid price is used for cost accounting, not his market score price
    other_p_cost = sum(p["price_current"] for p in result["squad"]["P"] if p["player_id"] != 1)
    assert result["total_cost"] == 20 + other_p_cost + sum(
        p["price_current"] for role in ("D", "C", "A") for p in result["squad"][role]
    )


def test_infeasible_when_budget_too_low():
    players_by_role = {
        "P": [_player(1, "P", 60, 100)],
        "D": [_player(10 + i, "D", 50 - i, 100) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 100) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 100) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=5, roster_player_ids=set(), taken_ids=set(),
        mode="from_scratch",
    )

    assert result["status"] == "infeasible"


def test_excludes_players_without_price():
    players_by_role = {
        "P": [_player(1, "P", 100, None), _player(2, "P", 10, 1),
              _player(3, "P", 10, 1), _player(4, "P", 10, 1)],
        "D": [_player(10 + i, "D", 10, 1) for i in range(8)],
        "C": [_player(30 + i, "C", 10, 1) for i in range(8)],
        "A": [_player(50 + i, "A", 10, 1) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_player_ids=set(), taken_ids=set(),
        mode="from_scratch",
    )

    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert 1 not in p_ids


def test_excludes_taken_players():
    players_by_role = {
        "P": [_player(1, "P", 100, 1), _player(2, "P", 10, 1),
              _player(3, "P", 10, 1), _player(4, "P", 10, 1)],
        "D": [_player(10 + i, "D", 10, 1) for i in range(8)],
        "C": [_player(30 + i, "C", 10, 1) for i in range(8)],
        "A": [_player(50 + i, "A", 10, 1) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_player_ids=set(), taken_ids={1},
        mode="from_scratch",
    )

    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert 1 not in p_ids
