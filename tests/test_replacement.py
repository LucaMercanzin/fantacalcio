from ranking.replacement import compute_replacement_advantage, compute_replacement_level
from ranking.lp_optimizer import ROLE_SLOTS


def _row(pid, score, role="D"):
    return {"player_id": pid, "score": score, "role_classic": role}


def test_replacement_level_is_nth_best_score_not_the_max():
    # P1-008: "replacement level" is the Nth-best (N = slots * teams), not
    # the single best alternative — with a tiny league_teams, the 2nd-best
    # score among D (8 slots/team) * 1 team = index 8 -> the 9th-ranked D.
    scores = list(range(100, 80, -1))  # 100..81, best-to-worst
    available = [_row(i, s) for i, s in enumerate(scores)]

    level = compute_replacement_level("D", available, league_teams=1)

    assert level == scores[ROLE_SLOTS["D"]]  # the 9th score (index 8) = 92


def test_replacement_level_falls_back_to_worst_when_pool_smaller_than_n():
    available = [_row(1, 90.0), _row(2, 70.0), _row(3, 55.0)]

    level = compute_replacement_level("D", available, league_teams=8)

    assert level == 55.0  # fewer candidates than ROLE_SLOTS["D"]*8 -> worst available


def test_replacement_level_zero_when_no_candidates():
    assert compute_replacement_level("D", [], league_teams=8) == 0.0


def test_replacement_advantage_positive_for_players_above_replacement_level():
    # Fewer than ROLE_SLOTS["D"]*1 candidates -> replacement level is the
    # worst score in the pool, so everyone above it gets a positive advantage
    # (P1-008 acceptance criterion: not just the #1 player).
    available = [_row(1, 90.0, "D"), _row(2, 70.0, "D"), _row(3, 55.0, "D")]

    assert compute_replacement_advantage(available[0], available, league_teams=1) > 0
    assert compute_replacement_advantage(available[1], available, league_teams=1) > 0
    # The worst player IS the replacement level: advantage is exactly 0, not negative.
    assert compute_replacement_advantage(available[2], available, league_teams=1) == 0.0
