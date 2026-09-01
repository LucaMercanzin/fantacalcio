"""Unit tests for the Rosa Ideale engine (ranking/ideal_squad.py) — the one
ranking module that had no dedicated test coverage (audit gap)."""

from ranking.ideal_squad import (
    BENCH_COVERAGE,
    FORMATIONS,
    build_ideal_squad,
    compare_starters_to_lp,
    compute_ideal_score,
)


def _row(player_id: int, role: str, score: float, price: float,
         appearances: int | None = 20, status: str | None = None,
         vfm_pct: float = 50.0) -> dict:
    return {
        "player_id": player_id,
        "canonical_name": f"Player {player_id}",
        "team": "Atalanta",
        "role_classic": role,
        "score": score,
        "decision_score": score,
        "value_for_money_percentile": vfm_pct,
        "value_for_money": 1.0,
        "price_current": price,
        "appearances": appearances,
        "status": status,
    }


def _players_by_role(rows: list[dict]) -> dict:
    by_role = {}
    for r in rows:
        by_role.setdefault(r["role_classic"], []).append(r)
    return by_role


def test_compute_ideal_score_uses_decision_score():
    player = _row(1, "C", score=100.0, price=20.0)
    score = compute_ideal_score(player)
    assert score > 0
    assert isinstance(score, float)


def test_compute_ideal_score_applies_injury_penalty():
    healthy = _row(1, "D", score=100.0, price=20.0)
    injured = _row(2, "D", score=100.0, price=20.0, status="infortunato")
    assert compute_ideal_score(injured) < compute_ideal_score(healthy)


def test_compute_ideal_score_does_not_double_count_fantasy_value_or_vfm():
    """P1-008/TASK-012: decision_score already blends fantasy_value and the
    value-for-money percentile (ranking.scorer.compute_decision_score) — an
    earlier version of compute_ideal_score summed them in again on top of
    it. Two players with the same decision_score but wildly different
    score/vfm_pct must land on the same ideal_score."""
    baseline = _row(1, "D", score=100.0, price=20.0, vfm_pct=50.0)
    baseline["decision_score"] = 60.0
    different_inputs = _row(2, "D", score=10.0, price=20.0, vfm_pct=95.0)
    different_inputs["decision_score"] = 60.0

    assert compute_ideal_score(baseline) == compute_ideal_score(different_inputs)

    missing_vfm = _row(3, "D", score=100.0, price=20.0)
    missing_vfm["decision_score"] = 60.0
    missing_vfm.pop("value_for_money_percentile")
    assert compute_ideal_score(missing_vfm) == compute_ideal_score(baseline)


def test_starters_prefer_roster_players_without_spending_budget():
    roster_ds = [_row(i, "D", score=90.0, price=30.0) for i in (1, 2, 3)]
    free_d = _row(4, "D", score=99.0, price=40.0)
    formation = {"P": 0, "D": 3, "C": 0, "A": 0}
    players = _players_by_role(roster_ds + [free_d])

    result = build_ideal_squad(
        players, formation, budget=500.0,
        roster_player_ids={1, 2, 3}, taken_ids=set(),
    )

    assert {p["player_id"] for p in result["starters"]["D"]} == {1, 2, 3}
    assert result["covered_by_roster"] == 3
    # bench picks the best free D for bench coverage, spending 40 of 500
    assert [p["player_id"] for p in result["bench"]["D"]] == [4]
    assert result["remaining_budget"] == 460.0


def test_free_candidates_respect_budget():
    expensive = _row(1, "P", score=99.0, price=30.0)
    affordable = _row(2, "P", score=60.0, price=10.0)
    formation = {"P": 1, "D": 0, "C": 0, "A": 0}

    result = build_ideal_squad(
        _players_by_role([expensive, affordable]), formation, budget=15.0,
        roster_player_ids=set(), taken_ids=set(),
    )

    assert [p["player_id"] for p in result["starters"]["P"]] == [2]
    assert result["remaining_budget"] == 5.0


def test_taken_players_are_never_selected():
    taken = _row(1, "A", score=99.0, price=10.0)
    free = _row(2, "A", score=80.0, price=10.0)
    formation = {"P": 0, "D": 0, "C": 0, "A": 1}

    result = build_ideal_squad(
        _players_by_role([taken, free]), formation, budget=500.0,
        roster_player_ids=set(), taken_ids={1},
    )

    assert [p["player_id"] for p in result["starters"]["A"]] == [2]


def test_injured_roster_player_sits_out_and_is_reported():
    injured = _row(1, "D", score=99.0, price=30.0, status="squalificato")
    backup = _row(2, "D", score=70.0, price=10.0)
    formation = {"P": 0, "D": 1, "C": 0, "A": 0}

    result = build_ideal_squad(
        _players_by_role([injured, backup]), formation, budget=500.0,
        roster_player_ids={1}, taken_ids=set(),
    )

    assert [p["player_id"] for p in result["starters"]["D"]] == [2]
    assert [p["player_id"] for p in result["unavailable_in_roster"]] == [1]
    # the injured player still fills the bench slot (existing behaviour)
    assert result["covered_by_roster"] == 1


def test_missing_counts_reflect_unfillable_slots():
    formation = {"P": 1, "D": 1, "C": 1, "A": 1}
    result = build_ideal_squad(
        _players_by_role([_row(1, "D", 80.0, 10.0)]), formation, budget=500.0,
        roster_player_ids=set(), taken_ids=set(),
    )

    assert result["missing"] == {"starters": 3, "bench": 7}


def test_bench_uses_bench_coverage_and_excludes_starters():
    ds = [_row(i, "D", score=80.0, price=10.0) for i in range(1, 6)]
    formation = {"P": 1, "D": 3, "C": 3, "A": 3}
    result = build_ideal_squad(
        _players_by_role(ds), formation, budget=500.0,
        roster_player_ids=set(), taken_ids=set(),
    )

    assert len(result["bench"]["D"]) == BENCH_COVERAGE["D"]
    used = {p["player_id"] for p in result["starters"]["D"] + result["bench"]["D"]}
    assert len(used) == len(result["starters"]["D"]) + len(result["bench"]["D"])


def test_an_expensive_early_role_does_not_starve_a_later_roles_budget():
    """Regression: build_ideal_squad used to drain one shared budget pool
    role-by-role in formation dict order (P, D, C, A) — an expensive P
    candidate (60, well above P's own 6% fair share of a 100-credit
    budget, but easily "affordable" from the whole undrained 100-credit
    pool) left too little of that shared pool for Attaccanti's turn, even
    though Attaccanti's own candidate (9) was a bargain relative to its
    own 46% fair share (46). On the real DB this left Attaccanti with 0 of
    3 starters while P/D/C had already spent nearly the whole budget
    between them. Each role must draw from its own reserved share."""
    formation = {"P": 1, "D": 1, "C": 1, "A": 1}
    players = _players_by_role([
        _row(1, "P", score=70.0, price=60.0),
        _row(2, "D", score=70.0, price=15.0),
        _row(3, "C", score=70.0, price=16.0),
        _row(4, "A", score=70.0, price=9.0),
    ])

    result = build_ideal_squad(
        players, formation, budget=100.0,
        roster_player_ids=set(), taken_ids=set(),
    )

    assert [p["player_id"] for p in result["starters"]["A"]] == [4]


def test_supported_formations_all_reach_eleven_starters():
    for name, formation in FORMATIONS.items():
        assert sum(formation.values()) == 11, name


def test_compare_starters_to_lp_uses_same_base_on_both_sides():
    """P1-015/TASK-030: summing Rosa Ideale's 11 starters + 7 bench (18)
    against the LP's full 25-player squad made the LP "win" by construction
    regardless of pick quality. Both sides must be exactly 11 (the formation
    size)."""
    formation = {"P": 1, "D": 3, "C": 4, "A": 3}
    starters = {
        "P": [_row(1, "P", score=50.0, price=10.0)],
        "D": [_row(i, "D", score=40.0, price=8.0) for i in range(2, 5)],
        "C": [_row(i, "C", score=45.0, price=12.0) for i in range(5, 9)],
        "A": [_row(i, "A", score=55.0, price=20.0) for i in range(9, 12)],
    }
    # LP squad has extra bench-quality players per role beyond the 11 needed —
    # only the top `formation[role]` per role should count.
    lp_squad = {
        "P": [_row(20, "P", score=48.0, price=9.0), _row(21, "P", score=10.0, price=1.0)],
        "D": [_row(i, "D", score=42.0, price=9.0) for i in range(22, 26)]
             + [_row(30, "D", score=5.0, price=1.0)],
        "C": [_row(i, "C", score=46.0, price=13.0) for i in range(31, 35)]
             + [_row(40, "C", score=5.0, price=1.0)],
        "A": [_row(i, "A", score=52.0, price=18.0) for i in range(41, 44)]
             + [_row(50, "A", score=5.0, price=1.0)],
    }

    result = compare_starters_to_lp(starters, lp_squad, formation)

    ideal_count = sum(len(v) for v in starters.values())
    lp_used = sorted(lp_squad["P"], key=lambda p: p["score"], reverse=True)[:1] \
        + sorted(lp_squad["D"], key=lambda p: p["score"], reverse=True)[:3] \
        + sorted(lp_squad["C"], key=lambda p: p["score"], reverse=True)[:4] \
        + sorted(lp_squad["A"], key=lambda p: p["score"], reverse=True)[:3]
    assert ideal_count == 11
    assert len(lp_used) == 11
    assert result["lp"]["score"] == round(sum(p["score"] for p in lp_used), 1)
    assert result["ideal"]["score"] == round(
        sum(p["score"] for role in starters for p in starters[role]), 1,
    )
    # The bench filler rows (score=5/10) must not leak into the LP total.
    assert result["lp"]["score"] < sum(p["score"] for role in lp_squad for p in lp_squad[role])


def test_compare_starters_to_lp_includes_cost():
    formation = {"P": 1, "D": 0, "C": 0, "A": 0}
    starters = {"P": [_row(1, "P", score=50.0, price=10.0)]}
    lp_squad = {"P": [_row(2, "P", score=48.0, price=9.0)]}

    result = compare_starters_to_lp(starters, lp_squad, formation)

    assert result["ideal"]["cost"] == 10.0
    assert result["lp"]["cost"] == 9.0
