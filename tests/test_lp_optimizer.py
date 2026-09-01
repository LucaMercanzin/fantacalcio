import pytest

from ranking.lp_optimizer import MAX_PLAYERS_PER_CLUB, ROLE_SLOTS, build_optimal_squad


def _player(pid, role, score, price, team=None, appearances=None):
    return {
        "player_id": pid, "canonical_name": f"Player {pid}", "role_classic": role,
        "score": score, "price_current": price, "team": team, "appearances": appearances,
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
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
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
        players_by_role, budget=25, roster_rows=[], taken_ids=set(),
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
    roster_rows = [
        {"player_id": 1, "role_classic": "P", "price_paid": 20,
         "canonical_name": "Player 1", "team": None},
    ]
    result = build_optimal_squad(
        players_by_role, budget=500 - 20, roster_rows=roster_rows, taken_ids=set(),
        mode="constrained",
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
        players_by_role, budget=5, roster_rows=[], taken_ids=set(),
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
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
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
        players_by_role, budget=500, roster_rows=[], taken_ids={1},
        mode="from_scratch",
    )

    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert 1 not in p_ids


@pytest.mark.parametrize("unproven_id", [4, 0])
def test_appearances_reliability_prefers_proven_over_unproven_at_equal_score(unproven_id):
    """TASK-016: at equal raw score, an unproven player (no appearances
    signal) must lose out to proven ones when the role has more
    equally-scored candidates than slots.

    Parametrized on the unproven player's id because the original
    single-case version of this test passed for the wrong reason: with every
    candidate in the role on the same score, every z-score was 0, so
    expected_points = z * reliability was 0 for all four and the assertion
    only held on CBC's tie-break over variable names. With the unproven
    keeper at id 0 the same code selected *him* over a proven one. The
    weighting is applied to the score before standardizing now, so this
    holds whatever the ids are."""
    players_by_role = {
        "P": [
            _player(1, "P", 80, 5, appearances=38),
            _player(2, "P", 80, 5, appearances=38),
            _player(3, "P", 80, 5, appearances=38),
            _player(unproven_id, "P", 80, 5, appearances=None),
        ],
        "D": [_player(10 + i, "D", 50, 1) for i in range(8)],
        "C": [_player(30 + i, "C", 50, 1) for i in range(8)],
        "A": [_player(50 + i, "A", 50, 1) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
        mode="from_scratch",
    )

    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert p_ids == {1, 2, 3}


def test_appearances_reliability_still_prefers_proven_below_the_role_average():
    """The same rule must hold for a pick from the bottom of the pool, which
    is where a mid-auction budget actually forces the solver to shop (on the
    real DB, from 200 credits down, 5 to 17 of the 25 picks sit below their
    role's mean). Multiplying an already-standardized z by reliability
    inverted the rule exactly there: for z < 0, a *lower* reliability makes
    the coefficient less negative, so the less reliable player won the slot.

    Two identical below-average keepers compete for the third slot: same
    score, same price, one proven and one who barely played."""
    players_by_role = {
        "P": [
            _player(1, "P", 90, 5, appearances=38),
            _player(2, "P", 90, 5, appearances=38),
            _player(3, "P", 60, 5, appearances=38),
            _player(4, "P", 60, 5, appearances=2),
        ],
        "D": [_player(10 + i, "D", 50, 1) for i in range(8)],
        "C": [_player(30 + i, "C", 50, 1) for i in range(8)],
        "A": [_player(50 + i, "A", 50, 1) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
        mode="from_scratch",
    )

    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert p_ids == {1, 2, 3}


def test_max_players_per_club_respects_cap():
    """P0-005/TASK-016: a club whose lineup craters (injuries, a bad run of
    form) shouldn't be able to sink half the roster — cap free-agent picks
    from any one club, even when that club's candidates are clearly the
    best available for a role."""
    players_by_role = {
        "P": [_player(1 + i, "P", 60, 1, team=f"PClub{i}") for i in range(3)],
        "D": (
            [_player(10 + i, "D", 100 - i, 1, team="Inter") for i in range(5)]
            + [_player(20 + i, "D", 50, 1, team=f"Club{i}") for i in range(5)]
        ),
        "C": [_player(30 + i, "C", 50, 1, team=f"ClubC{i}") for i in range(8)],
        "A": [_player(50 + i, "A", 50, 1, team=f"ClubA{i}") for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
        mode="from_scratch",
    )

    d_teams = [p["team"] for p in result["squad"]["D"]]
    assert d_teams.count("Inter") <= MAX_PLAYERS_PER_CLUB
    assert len(result["squad"]["D"]) == ROLE_SLOTS["D"]


def test_zscore_normalization_prevents_cross_role_scale_bias():
    """P0-005/TASK-016: before normalization, whichever role's raw score
    happened to sit on a numerically larger scale (e.g. attaccanti's
    fantamedia*10 baseline naturally runs higher than portieri's) always won
    any budget trade-off, regardless of how good a pick actually was
    *relative to its own role*. Z-score normalization is scale-invariant:
    uniformly inflating one role's raw scores 1000x must not change who
    gets picked when a tight budget forces a real cross-role choice."""
    def _build(a_scale: float):
        players_by_role = {
            "P": [
                _player(1, "P", 88, 1), _player(2, "P", 89, 1),
                _player(3, "P", 90, 1), _player(4, "P", 99, 50),
            ],
            "D": [_player(10 + i, "D", 50, 1) for i in range(8)],
            "C": [_player(30 + i, "C", 50, 1) for i in range(8)],
            "A": [_player(50 + i, "A", (10 + i * 10) * a_scale, 1) for i in range(6)]
                 + [_player(60, "A", 70 * a_scale, 50)],
        }
        return build_optimal_squad(
            players_by_role, budget=74, roster_rows=[], taken_ids=set(),
            mode="from_scratch",
        )

    normal = _build(a_scale=1)
    inflated = _build(a_scale=1000)

    assert normal["status"] == "optimal"
    normal_ids = {p["player_id"] for players in normal["squad"].values() for p in players}
    inflated_ids = {p["player_id"] for players in inflated["squad"].values() for p in players}
    assert normal_ids == inflated_ids


def test_roster_player_missing_from_pool_is_kept_fixed_and_costed():
    """P1-013/TASK-017: a roster player filtered out of get_ranked_role's
    pool (thin appearances, single source, foreign team...) must still
    count as filled for his role, still cost what was paid, and be
    surfaced in roster_not_in_pool - not silently dropped, which used to
    both understate total_cost and let the solver buy a 26th player."""
    players_by_role = {
        "P": [_player(2, "P", 40, 5), _player(3, "P", 30, 5)],  # player 1 absent
        "D": [_player(10 + i, "D", 50 - i, 5) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 5) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 6) for i in range(6)],
    }
    roster_rows = [
        {"player_id": 1, "role_classic": "P", "price_paid": 20,
         "canonical_name": "Ghost Player", "team": "Estero"},
    ]

    result = build_optimal_squad(
        players_by_role, budget=500 - 20, roster_rows=roster_rows, taken_ids=set(),
        mode="constrained",
    )

    assert result["status"] == "optimal"
    # Exactly 2 more P bought (3 slots total, 1 already filled by the
    # roster player) - not 3, which would make a 26-player squad.
    assert len(result["squad"]["P"]) == 3
    p_ids = {p["player_id"] for p in result["squad"]["P"]}
    assert p_ids == {1, 2, 3}
    ghost = next(p for p in result["squad"]["P"] if p["player_id"] == 1)
    assert ghost["canonical_name"] == "Ghost Player"
    assert ghost["score"] is None  # honestly unknown, not fabricated
    assert result["roster_not_in_pool"] == [1]
    other_p_cost = sum(p["price_current"] for p in result["squad"]["P"] if p["player_id"] != 1)
    assert result["total_cost"] == 20 + other_p_cost + sum(
        p["price_current"] for role in ("D", "C", "A") for p in result["squad"][role]
    )


def test_roster_not_in_pool_empty_when_all_roster_players_found():
    players_by_role = {
        "P": [_player(1, "P", 60, 10), _player(2, "P", 40, 5), _player(3, "P", 30, 5)],
        "D": [_player(10 + i, "D", 50 - i, 5) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 5) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 5) for i in range(6)],
    }
    roster_rows = [
        {"player_id": 1, "role_classic": "P", "price_paid": 20,
         "canonical_name": "Player 1", "team": None},
    ]

    result = build_optimal_squad(
        players_by_role, budget=500 - 20, roster_rows=roster_rows, taken_ids=set(),
        mode="constrained",
    )

    assert result["roster_not_in_pool"] == []


def test_infeasible_includes_a_reason():
    players_by_role = {
        "P": [_player(1, "P", 60, 100)],
        "D": [_player(10 + i, "D", 50 - i, 100) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 100) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 100) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=5, roster_rows=[], taken_ids=set(),
        mode="from_scratch",
    )

    assert result["status"] == "infeasible"
    assert result.get("reason")


def test_infeasible_reason_names_the_understaffed_role():
    players_by_role = {
        "P": [_player(1, "P", 60, 5)],  # only 1 candidate, 3 slots needed
        "D": [_player(10 + i, "D", 50 - i, 5) for i in range(8)],
        "C": [_player(30 + i, "C", 50 - i, 5) for i in range(8)],
        "A": [_player(50 + i, "A", 50 - i, 5) for i in range(6)],
    }

    result = build_optimal_squad(
        players_by_role, budget=500, roster_rows=[], taken_ids=set(),
        mode="from_scratch",
    )

    assert result["status"] == "infeasible"
    assert "P" in result["reason"]


def test_duplicate_candidate_across_roles_raises():
    """P1-013/TASK-017 point 3: roles are disjoint by construction (one
    role_classic per player) - a player appearing in two role's candidate
    lists means the caller built players_by_role incorrectly."""
    import pytest

    dup = _player(1, "D", 50, 5)
    players_by_role = {
        "P": [_player(2, "P", 60, 5), _player(3, "P", 50, 5), _player(4, "P", 40, 5)],
        "D": [dup] + [_player(10 + i, "D", 50 - i, 5) for i in range(1, 8)],
        "C": [{**dup, "role_classic": "C"}] + [_player(30 + i, "C", 50 - i, 5) for i in range(1, 8)],
        "A": [_player(50 + i, "A", 50 - i, 5) for i in range(6)],
    }

    with pytest.raises(AssertionError):
        build_optimal_squad(
            players_by_role, budget=500, roster_rows=[], taken_ids=set(),
            mode="from_scratch",
        )
