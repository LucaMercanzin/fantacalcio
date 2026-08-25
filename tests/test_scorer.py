from ranking.scorer import (
    compute_score, rank_players, compute_player_quality, compute_risk,
    compute_value_for_money, compute_decision_score, enrich_scores,
)


def test_compute_score_uses_fantamedia_when_present():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 0


def test_compute_score_falls_back_to_avg_rating():
    row = {"fantamedia": None, "avg_rating": 6.0, "appearances": None, "status": "ok"}
    score = compute_score(row)
    assert score == 6.0 * 10 + 0.5 * 5 - 0


def test_compute_score_penalizes_injured_status():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "infortunato"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 15


def test_compute_score_penalizes_unproven_low_appearances():
    # A source-default "neutral" fantamedia (6.0) backed by a single
    # appearance shouldn't outrank a real starter with a genuinely lower
    # but proven average (regression: was ranking above real starters).
    unproven = {"fantamedia": 6.0, "avg_rating": None, "appearances": 1, "status": "ok"}
    proven_starter = {"fantamedia": 5.7, "avg_rating": None, "appearances": 30, "status": "ok"}
    assert compute_score(unproven) < compute_score(proven_starter)


def test_compute_score_unproven_penalty_fades_out_by_threshold():
    at_threshold = {"fantamedia": 6.0, "avg_rating": None, "appearances": 5, "status": "ok"}
    full_season = {"fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    # no unproven penalty left at the threshold — only the reliability bonus differs
    assert compute_score(at_threshold) == 60.0 + (5 / 38) * 5
    assert compute_score(full_season) == 60.0 + 5.0


def test_rank_players_orders_best_to_worst():
    rows = [
        {"canonical_name": "Low", "fantamedia": 5.0, "avg_rating": None, "appearances": 38, "status": "ok"},
        {"canonical_name": "High", "fantamedia": 8.0, "avg_rating": None, "appearances": 38, "status": "ok"},
    ]

    ranked = rank_players(rows)

    assert [r["canonical_name"] for r in ranked] == ["High", "Low"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_compute_player_quality_independent_of_price():
    strong_defender = {"avg_rating": 6.5, "fantamedia": 5.5}
    assert compute_player_quality(strong_defender) == 50.0


def test_compute_risk_high_when_injured_and_unreliable():
    row = {"appearances": 5, "status": "infortunato"}
    risk = compute_risk(row)
    assert risk > compute_risk({"appearances": 38, "status": "ok"})


def test_compute_risk_unchanged_when_fcp_signals_missing():
    row = {"appearances": 38, "status": "ok"}
    assert compute_risk(row) == compute_risk({"appearances": 38, "status": "ok"})


def test_compute_risk_higher_with_low_fcp_stability():
    base = {"appearances": 38, "status": "ok"}
    low_stability = {
        **base, "investment_stability_pct": 20, "injury_resistance_pct": 20,
    }
    high_stability = {
        **base, "investment_stability_pct": 90, "injury_resistance_pct": 90,
    }
    assert compute_risk(low_stability) > compute_risk(high_stability)
    assert compute_risk(low_stability) > compute_risk(base)


def test_enrich_scores_exposes_alg_fcp_without_affecting_score():
    row = {
        "fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "alg_fcp": 90,
    }
    enriched = enrich_scores(row)
    assert enriched["alg_fcp"] == 90
    assert enriched["score"] == compute_score(row)


def test_compute_value_for_money_none_without_price():
    assert compute_value_for_money(50.0, None) is None
    assert compute_value_for_money(50.0, 0) is None


def test_compute_value_for_money_floors_price_for_minimum_credit_players():
    # A 1-credit bench player and a 5-credit player should score identically
    # on value-for-money — dividing by the raw 1-credit price would make the
    # bench player look like an incredible bargain, which it isn't.
    at_floor = compute_value_for_money(50.0, 1)
    at_min_price = compute_value_for_money(50.0, 5)
    assert at_floor == at_min_price


def test_compute_value_for_money_higher_for_cheaper_player():
    cheap = compute_value_for_money(50.0, 10)
    expensive = compute_value_for_money(50.0, 40)
    assert cheap > expensive


def test_compute_decision_score_penalizes_risk():
    safe = compute_decision_score(70.0, 20.0, risk=10, confidence=90)
    risky = compute_decision_score(70.0, 20.0, risk=80, confidence=90)
    assert safe > risky


def test_enrich_scores_a_good_but_unaffordable_player_can_score_low_on_value():
    row = {
        "fantamedia": 8.0, "avg_rating": 7.5, "appearances": 38, "status": "ok",
        "price_current": 60, "confidence": 90,
    }
    enriched = enrich_scores(row)

    assert enriched["player_quality"] > 80
    # strong player, but expensive: value-for-money shouldn't also be top-tier
    assert enriched["value_for_money"] < enriched["player_quality"]
