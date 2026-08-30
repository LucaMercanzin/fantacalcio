from ranking.goalkeeper_score import compute_goalkeeper_score
from ranking.scorer import compute_score


def _row(**overrides):
    row = {
        "role_classic": "P", "fantamedia": 6.0, "avg_rating": 6.2,
        "appearances": 30, "status": "ok",
        "season_goals_conceded": 30, "team_xga": 1.3,
    }
    row.update(overrides)
    return row


def test_returns_none_without_a_real_fantamedia():
    """Same insufficient_data gate as compute_score/P0-002 — a fabricated
    score off avg_rating/goals_conceded alone would reopen the exact bug
    TASK-002 fixed."""
    row = _row(fantamedia=None)
    assert compute_goalkeeper_score(row) is None


def test_compute_score_delegates_to_goalkeeper_score_for_role_p():
    row = _row()
    assert compute_score(row) == compute_goalkeeper_score(row)


def test_fewer_goals_conceded_per_appearance_scores_higher():
    strong_defense = _row(season_goals_conceded=15, appearances=30)  # 0.5/match
    weak_defense = _row(season_goals_conceded=55, appearances=30)  # 1.83/match

    assert compute_goalkeeper_score(strong_defense) > compute_goalkeeper_score(weak_defense)


def test_lower_team_xga_scores_higher_all_else_equal():
    strong_team = _row(team_xga=0.9)
    weak_team = _row(team_xga=2.0)

    assert compute_goalkeeper_score(strong_team) > compute_goalkeeper_score(weak_team)


def test_missing_goals_conceded_and_team_xga_fall_back_to_neutral_not_a_crash():
    row = _row(season_goals_conceded=None, team_xga=None)
    score = compute_goalkeeper_score(row)
    assert score is not None


def test_score_stays_on_the_same_scale_as_outfield_compute_score():
    """Rosa Ideale/the LP optimizer sum "score" across roles — a portiere's
    score must land in the same rough band as an outfield player's, not on
    a different scale entirely."""
    goalkeeper = _row(avg_rating=7.0, season_goals_conceded=18, appearances=35, team_xga=1.0)
    outfield = {"fantamedia": 6.8, "appearances": 35, "status": "ok", "role_classic": "C"}

    gk_score = compute_score(goalkeeper)
    outfield_score = compute_score(outfield)

    assert 40 <= gk_score <= 100
    assert abs(gk_score - outfield_score) < 30


def test_reliability_bonus_still_rewards_appearances_like_outfield_players():
    nailed_on = _row(appearances=38)
    barely_played = _row(appearances=5)

    assert compute_goalkeeper_score(nailed_on) > compute_goalkeeper_score(barely_played)


def test_injured_status_is_penalized():
    healthy = _row(status="ok")
    injured = _row(status="infortunato")

    assert compute_goalkeeper_score(injured) < compute_goalkeeper_score(healthy)
