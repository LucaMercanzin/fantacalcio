"""Unit tests for the Rosa Ideale engine (ranking/ideal_squad.py) — the one
ranking module that had no dedicated test coverage (audit gap)."""

from ranking.ideal_squad import BENCH_COVERAGE, FORMATIONS, build_ideal_squad, compute_ideal_score


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


def test_compute_ideal_score_uses_score_and_vfm():
    player = _row(1, "C", score=100.0, price=20.0)
    score = compute_ideal_score(player)
    assert score > 0
    assert isinstance(score, float)


def test_compute_ideal_score_defaults_vfm_and_applies_injury_penalty():
    healthy = _row(1, "D", score=100.0, price=20.0)
    injured = _row(2, "D", score=100.0, price=20.0, status="infortunato")
    assert compute_ideal_score(injured) < compute_ideal_score(healthy)

    no_vfm = _row(3, "D", score=100.0, price=20.0)
    no_vfm.pop("value_for_money_percentile")
    assert compute_ideal_score(no_vfm) == compute_ideal_score(healthy)


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


def test_supported_formations_all_reach_eleven_starters():
    for name, formation in FORMATIONS.items():
        assert sum(formation.values()) == 11, name